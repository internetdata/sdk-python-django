"""The adapter, through a real Django request cycle, plus the shared corpus.

A test client connects from ``127.0.0.1``, which is a bogon and is answered locally
without a request. Anything that needs a served answer therefore has to arrive wearing
a public address, through a selector.
"""

from __future__ import annotations

import json
import os
import pathlib
from typing import Any

import django
import httpx
import pytest
from django.conf import settings

settings.configure(
    DEBUG=True,
    SECRET_KEY="test",
    ALLOWED_HOSTS=["*"],
    ROOT_URLCONF=__name__,
    MIDDLEWARE=["internetdata_django.InternetDataMiddleware"],
    DATABASES={},
    INTERNETDATA={},
)
django.setup()

from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, JsonResponse
from django.test import Client, RequestFactory
from django.urls import path
from internetdata import InternetData

from internetdata_django import (
    InternetDataMiddleware,
    block_if,
    default_ip_selector,
    header_ip_selector,
    lookup,
    xff_ip_selector,
)

CORPUS = json.loads(
    (pathlib.Path(__file__).parent.parent / "testdata/testdata.json").read_text()
)
MIDDLEWARE = CORPUS["middleware"]
# Served answers from the lookup corpus: Unlimited's, and a paid plan's.
ANSWERS: dict[str, dict[str, Any]] = {case["name"]: case["body"] for case in CORPUS["lookup"]}
UNLIMITED = ANSWERS["unlimited-answer"]
PAID = ANSWERS["paid-full-shape"]
PUBLIC_IP = PAID["ip"]
EMBARGO = {"location": {"country": ["DE", "AT"]}}


def view(request: Any) -> JsonResponse:
    found = lookup(request)
    result = found.result if found else None
    return JsonResponse(
        {
            "ip": found.ip if found else None,
            "country": result.location.country if result else None,
            "is_vpn": result.is_vpn if result else None,
            "is_bogon": result.is_bogon if result else None,
            "error": type(found.error).__name__ if found and found.error else None,
            "attached": found is not None,
        }
    )


@block_if(EMBARGO)
def guarded(request: Any) -> JsonResponse:
    return view(request)


@block_if(EMBARGO)
async def guarded_async(request: Any) -> JsonResponse:
    return view(request)


@block_if(
    EMBARGO,
    on_blocked=lambda request, found: JsonResponse(
        {"why": found.result.location.country}, status=451
    ),
)
def guarded_custom(request: Any) -> JsonResponse:
    return view(request)


@block_if(EMBARGO, fail_closed=True)
def guarded_closed(request: Any) -> JsonResponse:
    return view(request)


# The corpus through the decorator: each case sets the condition, and the guard is
# built per request so its warn-once starts clean.
CASE: dict[str, Any] = {}


def corpus(request: Any) -> JsonResponse:
    return block_if(CASE["condition"], on_warn=CASE["warnings"].append)(view)(request)  # type: ignore[no-any-return]


urlpatterns = [
    path("", view),
    path("guarded", guarded),
    path("guarded-async", guarded_async),
    path("guarded-custom", guarded_custom),
    path("guarded-closed", guarded_closed),
    path("corpus", corpus),
]


def serving(body: dict[str, Any], *, status: int = 200) -> InternetData:
    """A client whose every answer is ``body`` for the address asked about, recording
    those addresses."""

    def handle(request: httpx.Request) -> httpx.Response:
        ip = request.url.path.lstrip("/")
        asked.append(ip)
        return httpx.Response(status, json={**body, "ip": ip})

    asked: list[str] = []
    client = InternetData(cache=False, retries=0, transport=httpx.MockTransport(handle))
    client.asked = asked  # type: ignore[attr-defined]
    return client


def call(headers: dict[str, str] | None = None, **options: Any) -> Any:
    settings.INTERNETDATA = options
    return Client(
        **{f"HTTP_{k.upper().replace('-', '_')}": v for k, v in (headers or {}).items()}
    )


def get(client: Any, url: str = "/") -> tuple[int, dict[str, Any]]:
    response = client.get(url)
    return response.status_code, json.loads(response.content or b"{}")


def fixed_ip(_request: Any) -> str:
    return PUBLIC_IP


def test_enriches_the_request_and_leaves_the_decision_to_the_app() -> None:
    client = serving(UNLIMITED)
    status, body = get(call(client=client, ip_selector=fixed_ip))
    assert status == 200
    assert body["attached"] is True
    assert body["country"] == "AT"
    assert body["is_vpn"] is None, "Unlimited leaves is_vpn out, and absent is not false"
    assert body["ip"] == PUBLIC_IP
    assert client.asked == [PUBLIC_IP]


def test_blocks_on_a_country_and_passes_another_country() -> None:
    status, body = get(
        call(client=serving(UNLIMITED), ip_selector=fixed_ip, block_condition=EMBARGO)
    )
    assert status == 403
    assert body == {"error": "access denied"}
    assert body.get("attached") is None, "the view answered a blocked request"

    status, _ = get(
        call(
            client=serving(UNLIMITED),
            ip_selector=fixed_ip,
            block_condition={"location": {"country": "DE"}},
        )
    )
    assert status == 200


def test_blocks_on_a_network_type_and_on_anonymity() -> None:
    status, _ = get(
        call(
            client=serving(UNLIMITED),
            ip_selector=fixed_ip,
            block_condition={"asn": {"type": "hosting"}},
        )
    )
    assert status == 403, "the network's type is served on every plan"

    status, _ = get(
        call(
            client=serving(PAID),
            ip_selector=fixed_ip,
            block_condition=[{"is_tor": True}, {"is_vpn": True}],
        )
    )
    assert status == 403


def test_a_condition_reaches_the_evidence_fields() -> None:
    status, _ = get(
        call(
            client=serving(PAID),
            ip_selector=fixed_ip,
            block_condition={"vpn": {"provider": "nordvpn"}},
        )
    )
    assert status == 200, "a different provider must not match"

    status, _ = get(
        call(
            client=serving(PAID),
            ip_selector=fixed_ip,
            block_condition={"vpn": {"provider": "MULLVAD"}},
        )
    )
    assert status == 403, "a provider must compare without case"


def test_on_blocked_replaces_the_refusal() -> None:
    status, body = get(
        call(
            client=serving(UNLIMITED),
            ip_selector=fixed_ip,
            block_condition=EMBARGO,
            on_blocked=lambda request, found: JsonResponse(
                {"why": found.result.location.country}, status=451
            ),
        )
    )
    assert status == 451
    assert body == {"why": "AT"}


def test_skip_leaves_the_request_untouched() -> None:
    client = serving(UNLIMITED)
    status, body = get(
        call(
            client=client,
            ip_selector=fixed_ip,
            block_condition=EMBARGO,
            skip=lambda request: request.path == "/",
        )
    )
    assert status == 200
    assert body["attached"] is False
    assert client.asked == []


def test_lookup_is_the_attached_answer_or_none() -> None:
    """``request.internetdata`` exists only on a request the middleware looked up, so a
    view reading it where ``skip`` applies would raise ``AttributeError``, a 500."""
    request = HttpRequest()
    assert lookup(request) is None
    request.internetdata = found = object()  # type: ignore[attr-defined]
    assert lookup(request) is found


def test_a_failing_lookup_lets_the_visitor_through() -> None:
    failing = serving({"error": "boom"}, status=500)
    status, body = get(call(client=failing, ip_selector=fixed_ip, block_condition=EMBARGO))
    assert status == 200
    assert body["error"] == "InternetDataError"


# The test that matters. Every other assertion here would pass whether or not the
# selector is right, because a direct connection has nothing to confuse.
def test_a_forged_x_forwarded_for_is_ignored_by_default() -> None:
    client = serving(UNLIMITED)
    _, body = get(call({"X-Forwarded-For": PUBLIC_IP}, client=client))
    assert body["ip"] == "127.0.0.1", "REMOTE_ADDR is the socket peer; the header is a forgery"
    assert client.asked == [], "and a bogon is answered locally, so nothing was asked"

    explicit = serving(UNLIMITED)
    _, body = get(
        call({"X-Forwarded-For": PUBLIC_IP}, client=explicit, ip_selector=xff_ip_selector())
    )
    assert body["ip"] == PUBLIC_IP
    assert explicit.asked == [PUBLIC_IP]


def test_a_header_selector_reads_the_edge_that_writes_it() -> None:
    client = serving(UNLIMITED)
    _, body = get(
        call(
            {"CF-Connecting-IP": "45.83.91.9"},
            client=client,
            ip_selector=header_ip_selector("CF-Connecting-IP"),
        )
    )
    assert body["ip"] == "45.83.91.9"
    assert client.asked == ["45.83.91.9"]


def test_depth_counts_trusted_hops_from_the_right() -> None:
    client = serving(UNLIMITED)
    get(
        call(
            {"X-Forwarded-For": f"{PUBLIC_IP}, 70.41.3.18, 150.172.238.178"},
            client=client,
            ip_selector=xff_ip_selector(1),
        )
    )
    assert client.asked == ["150.172.238.178"]


def test_a_private_client_address_is_answered_locally_and_never_blocks() -> None:
    client = serving(UNLIMITED)
    status, body = get(
        call(
            client=client,
            block_condition={"asn": {"type": "hosting"}},
            ip_selector=default_ip_selector,
        )
    )
    assert status == 200, "local development must not lock you out of your own app"
    assert body["is_bogon"] is True
    assert client.asked == []


def test_a_condition_that_constrains_nothing_is_refused_at_construction() -> None:
    settings.INTERNETDATA = {"block_condition": {"is_vpn": False}}
    with pytest.raises(ValueError, match="constrains nothing"):
        InternetDataMiddleware(lambda request: JsonResponse({}))


@pytest.mark.parametrize("case", MIDDLEWARE["conditions"], ids=lambda c: c["name"])
def test_corpus_conditions(case: dict[str, Any]) -> None:
    ip = case.get("bogon") or case["body"]["ip"]
    client = serving(case.get("body") or {})
    warnings: list[str] = []
    status, _ = get(
        call(
            client=client,
            ip_selector=lambda _request, ip=ip: ip,
            block_condition=case["condition"],
            on_warn=warnings.append,
        )
    )
    assert status == (403 if case["expect"]["blocked"] else 200), case["why"]
    reported = [w for w in warnings if "does not include" in w]
    assert len(reported) == (1 if case["expect"]["missing"] else 0), case["why"]
    for member in case["expect"]["missing"]:
        assert member in reported[0], case["why"]


def test_block_if_refuses_only_the_view_it_decorates() -> None:
    client = serving(UNLIMITED)
    browser = call(client=client, ip_selector=fixed_ip)
    status, body = get(browser, "/guarded")
    assert status == 403
    assert body == {"error": "access denied"}
    status, body = get(browser, "/")
    assert status == 200, "the middleware itself has no condition, so other views are open"
    assert body["country"] == "AT"
    assert client.asked == [PUBLIC_IP, PUBLIC_IP], (
        "one lookup per request, none by the decorator"
    )

    elsewhere = serving({**UNLIMITED, "location": {**UNLIMITED["location"], "country": "FR"}})
    status, body = get(call(client=elsewhere, ip_selector=fixed_ip), "/guarded")
    assert status == 200
    assert body["attached"] is True


def test_block_if_guards_an_async_view() -> None:
    status, body = get(call(client=serving(UNLIMITED), ip_selector=fixed_ip), "/guarded-async")
    assert status == 403
    assert body == {"error": "access denied"}

    elsewhere = serving({**UNLIMITED, "location": {**UNLIMITED["location"], "country": "FR"}})
    status, _ = get(call(client=elsewhere, ip_selector=fixed_ip), "/guarded-async")
    assert status == 200


def test_block_if_on_blocked_replaces_the_refusal() -> None:
    status, body = get(call(client=serving(UNLIMITED), ip_selector=fixed_ip), "/guarded-custom")
    assert status == 451
    assert body == {"why": "AT"}


def test_block_if_lets_a_skipped_request_through() -> None:
    client = serving(UNLIMITED)
    status, body = get(
        call(client=client, ip_selector=fixed_ip, skip=lambda request: True), "/guarded"
    )
    assert status == 200
    assert body["attached"] is False
    assert client.asked == []


def test_block_if_fails_open_unless_told_to_fail_closed() -> None:
    failing = serving({"error": "boom"}, status=500)
    status, body = get(call(client=failing, ip_selector=fixed_ip), "/guarded")
    assert status == 200
    assert body["error"] == "InternetDataError"

    status, body = get(call(client=failing, ip_selector=fixed_ip), "/guarded-closed")
    assert status == 403
    assert body == {"error": "access denied"}


def test_block_if_without_the_middleware_is_a_configuration_error() -> None:
    request = RequestFactory().get("/guarded")
    with pytest.raises(ImproperlyConfigured, match="InternetDataMiddleware"):
        guarded(request)


def test_block_if_refuses_a_condition_that_constrains_nothing() -> None:
    with pytest.raises(ValueError, match="constrains nothing"):
        block_if({"is_vpn": False})(view)


def test_block_if_warns_once_naming_the_view() -> None:
    warnings: list[str] = []

    @block_if({"location": {"city": "Vienna"}}, on_warn=warnings.append)
    def city(request: Any) -> JsonResponse:
        return view(request)

    settings.INTERNETDATA = {"client": serving(UNLIMITED), "ip_selector": fixed_ip}
    for _ in range(2):
        request = RequestFactory().get("/")
        InternetDataMiddleware(city)(request)
    assert len(warnings) == 1
    assert "block_if on test_block_if_warns_once_naming_the_view.<locals>.city" in warnings[0]
    assert "location.city" in warnings[0]


@pytest.mark.parametrize("case", MIDDLEWARE["conditions"], ids=lambda c: c["name"])
def test_corpus_conditions_through_block_if(case: dict[str, Any]) -> None:
    ip = case.get("bogon") or case["body"]["ip"]
    client = serving(case.get("body") or {})
    CASE.update(condition=case["condition"], warnings=[])
    status, _ = get(call(client=client, ip_selector=lambda _request, ip=ip: ip), "/corpus")
    assert status == (403 if case["expect"]["blocked"] else 200), case["why"]
    reported = [w for w in CASE["warnings"] if "does not include" in w]
    assert len(reported) == (1 if case["expect"]["missing"] else 0), case["why"]
    for member in case["expect"]["missing"]:
        assert member in reported[0], case["why"]


# Built exactly as the README builds it: the key from the environment and nothing else.
# Every other test hands the middleware a client, so none of them could see a core that
# cannot start from a key alone. The test client's loopback peer is a bogon, answered
# with no request.
@pytest.mark.parametrize("key", ["a-key", None])
def test_the_middleware_starts_the_way_the_readme_builds_it(
    monkeypatch: pytest.MonkeyPatch, key: str | None
) -> None:
    if key is None:
        monkeypatch.delenv("INTERNETDATA_API_KEY", raising=False)
    else:
        monkeypatch.setenv("INTERNETDATA_API_KEY", key)
    status, body = get(call(api_key=os.environ.get("INTERNETDATA_API_KEY")))

    assert status == 200
    assert body["attached"] is True
    assert body["is_bogon"] is True
    assert body["error"] is None


GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


@block_if({"is_hosting": True})
def guarded_hosting(request: Any) -> JsonResponse:
    return view(request)


urlpatterns.append(path("guarded-hosting", guarded_hosting))


def api_answering(
    monkeypatch: pytest.MonkeyPatch, verdicts: dict[str, str] | None
) -> list[str | None]:
    """The API's host, answering every lookup as a match for ``{"is_hosting": True}`` and,
    for a sent agent, with the verdict ``verdicts`` holds for it (None: no verdict, as
    Unlimited answers). Returns the ``user_agent`` each lookup sent."""
    sent: list[str | None] = []

    def handle(_transport: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
        if request.url.host != "api.internetdata.io":
            raise httpx.ConnectError("only the API's host answers here", request=request)
        agent = request.url.params.get("user_agent")
        sent.append(agent)
        body: dict[str, Any] = {**PAID, "ip": request.url.path.lstrip("/"), "is_hosting": True}
        if agent and verdicts is not None:
            verdict = verdicts.get(agent, "not_bot")
            body["user_agent"] = {"agent": "Googlebot", "kind": "bot", "verdict": verdict}
        return httpx.Response(200, json=body)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle)
    monkeypatch.setenv("INTERNETDATA_API_KEY", "a-key")
    return sent


def visit(user_agent: str | None, url: str = "/", peer: str = PUBLIC_IP, **options: Any) -> int:
    """One request through the README's settings, plus ``options``."""
    headers = {} if user_agent is None else {"User-Agent": user_agent}
    client = call(headers, api_key=os.environ["INTERNETDATA_API_KEY"], **options)
    return int(client.get(url, REMOTE_ADDR=peer).status_code)


def test_allow_bots_sends_the_requests_own_user_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent = api_answering(monkeypatch, {GOOGLEBOT: "verified"})

    visit(GOOGLEBOT, allow_bots=True)
    visit("", peer="45.83.91.2", allow_bots=True)
    visit(None, peer="45.83.91.3", allow_bots=True)

    assert sent == [GOOGLEBOT, None, None], "an empty or absent header sent an agent"


def test_without_allow_bots_no_user_agent_is_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = api_answering(monkeypatch, {GOOGLEBOT: "verified"})

    status = visit(GOOGLEBOT, block_condition={"is_hosting": True})

    assert sent == [None]
    assert status == 403


@pytest.mark.parametrize(
    ("verdict", "status"), [("verified", 200), ("spoofed", 403), ("not_bot", 403)]
)
@pytest.mark.parametrize("url", ["/", "/guarded-hosting"])
def test_a_verified_crawler_passes_a_condition_it_meets_and_no_other_does(
    monkeypatch: pytest.MonkeyPatch, url: str, verdict: str, status: int
) -> None:
    api_answering(monkeypatch, {GOOGLEBOT: verdict})
    options: dict[str, Any] = {"allow_bots": True}
    if url == "/":
        options["block_condition"] = {"is_hosting": True}

    assert visit(GOOGLEBOT, url=url, **options) == status


def test_a_condition_naming_the_verdict_refuses_a_forged_crawler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_answering(monkeypatch, {GOOGLEBOT: "spoofed"})

    status = visit(
        GOOGLEBOT, allow_bots=True, block_condition={"user_agent": {"verdict": "spoofed"}}
    )

    assert status == 403


def test_an_answer_without_a_verdict_warns_once(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = api_answering(monkeypatch, None)
    warnings: list[str] = []
    settings.INTERNETDATA = {
        "api_key": os.environ["INTERNETDATA_API_KEY"],
        "allow_bots": True,
        "on_warn": warnings.append,
    }
    client = Client(HTTP_USER_AGENT=GOOGLEBOT)

    client.get("/", REMOTE_ADDR=PUBLIC_IP)
    client.get("/", REMOTE_ADDR="45.83.91.2")

    assert sent == [GOOGLEBOT, GOOGLEBOT]
    assert len([w for w in warnings if "user_agent verdict" in w]) == 1, warnings


# The README's middleware again, served a PUBLIC peer with a forged X-Forwarded-For: the
# key must reach the API when it is set and no Authorization go out when it is not, and
# the socket address must be the one looked up. The test above is answered with no
# request, so it passed with the key dropped. httpx's own transport answers for the API's
# host alone, so nothing leaves the machine.
@pytest.mark.parametrize("key", ["a-key", None])
def test_the_readme_middleware_sends_its_key_for_a_public_peer(
    monkeypatch: pytest.MonkeyPatch, key: str | None
) -> None:
    sent: list[tuple[str, str | None]] = []

    def handle(_transport: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
        if request.url.host != "api.internetdata.io":
            raise httpx.ConnectError("only the API's host answers here", request=request)
        sent.append((request.url.path, request.headers.get("Authorization")))
        return httpx.Response(200, json={**UNLIMITED, "ip": PUBLIC_IP})

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle)
    if key is None:
        monkeypatch.delenv("INTERNETDATA_API_KEY", raising=False)
    else:
        monkeypatch.setenv("INTERNETDATA_API_KEY", key)
    client = call(
        {"X-Forwarded-For": "1.1.1.1"}, api_key=os.environ.get("INTERNETDATA_API_KEY")
    )
    response = client.get("/", REMOTE_ADDR=PUBLIC_IP)
    status, body = response.status_code, json.loads(response.content)

    assert status == 200
    assert body["ip"] == PUBLIC_IP, "the socket peer is looked up; the header is a forgery"
    assert body["error"] is None and body["country"] == "AT"
    assert len(sent) == 1 and sent[0][0].endswith(PUBLIC_IP)
    assert sent[0][1] == (f"Bearer {key}" if key else None)


# The bot flag arrived with a re-pin: the README's middleware with a condition on it,
# served a PUBLIC peer, refuses a crawler's address and lets a person's through, with no
# warning, since every plan answers it.
def test_a_condition_on_the_bot_flag_refuses_a_bot_from_a_public_peer(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    bot = ANSWERS["paid-bot"]
    served = {bot["ip"]: bot, PUBLIC_IP: {**UNLIMITED, "ip": PUBLIC_IP}}
    sent: list[str] = []

    def handle(_transport: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
        if request.url.host != "api.internetdata.io":
            raise httpx.ConnectError("only the API's host answers here", request=request)
        ip = request.url.path.lstrip("/")
        sent.append(ip)
        return httpx.Response(200, json=served[ip])

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle)
    monkeypatch.setenv("INTERNETDATA_API_KEY", "a-key")
    client = call(
        api_key=os.environ.get("INTERNETDATA_API_KEY"), block_condition={"is_bot": True}
    )
    statuses = [
        client.get("/", REMOTE_ADDR=peer).status_code for peer in (bot["ip"], PUBLIC_IP)
    ]

    assert statuses == [403, 200]
    assert sent == [bot["ip"], PUBLIC_IP]
    assert not [r for r in caplog.records if "is_bot" in r.getMessage()], "no member is missing"
