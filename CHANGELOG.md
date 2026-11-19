# Changelog

What each release changed for you, newest first. Each line is a commit's summary, linked to its full description and diff.

## 1.0.3 - 2026-11-19

### Fixes

- Require internetdata 2.15.2: a reduced answer is cached a minute at most ([`30ff032`](https://github.com/internetdata/sdk-python-django/commit/30ff032f4eab2163d3e36be9734f68384017fb00))

## 1.0.2 - 2026-11-19

### Fixes

- Require internetdata 2.15.1: cap_reached on a paid answer past its overage cap ([`f25d51a`](https://github.com/internetdata/sdk-python-django/commit/f25d51a780e71773d5e6ac572e84577dc767db3f))

## 1.0.1 - 2026-11-14

### Fixes

- Require internetdata 2.12.1: a 403 can mean the key lacks the ip.lookup scope ([`6b8bf50`](https://github.com/internetdata/sdk-python-django/commit/6b8bf5023bad783e237a96667efb3d50063d5598))

## 1.0.0 - 2026-11-14

### Features

- Attach the visitor's InternetData record to every request as `request.internetdata`: the location, the network and the company behind the address, and the anonymity and hosting flags your plan serves ([`c47a7c1`](https://github.com/internetdata/sdk-python-django/commit/c47a7c186f1b126400bbb6e1163069acafde33a4))
- Refuse a request with a `block_condition` in `settings.INTERNETDATA`, written in the shape of a result, by country, network type, anonymity or any other member, with 403 or an `on_blocked` of your own ([`c47a7c1`](https://github.com/internetdata/sdk-python-django/commit/c47a7c186f1b126400bbb6e1163069acafde33a4))
- Refuse one view with the `block_if` decorator, sync or async, judging the answer the middleware already attached ([`c47a7c1`](https://github.com/internetdata/sdk-python-django/commit/c47a7c186f1b126400bbb6e1163069acafde33a4))
- Choose where the client address comes from: `REMOTE_ADDR` by default, `xff_ip_selector`, `header_ip_selector` for a header your edge writes, or a callable of your own ([`c47a7c1`](https://github.com/internetdata/sdk-python-django/commit/c47a7c186f1b126400bbb6e1163069acafde33a4))
- Fail open on any lookup failure unless `fail_closed` is set, with a 2.5 s bound, no retry and a cache by default ([`c47a7c1`](https://github.com/internetdata/sdk-python-django/commit/c47a7c186f1b126400bbb6e1163069acafde33a4))
