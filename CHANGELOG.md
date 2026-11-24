# Changelog

What each release changed for you, newest first. Each line is a commit's summary, linked to its full description and diff.

## 1.0.8 - 2026-11-24

### Features

- Require internetdata 2.19.0: a block condition matches any element of a list member ([`b648ad5`](https://github.com/internetdata/sdk-python-django/commit/b648ad5eea7b02818bbde510438eab40be54ccb7))

## 1.0.7 - 2026-11-23

### Fixes

- Require internetdata 2.18.1: whose operator an unverified bot names ([`b92ac6f`](https://github.com/internetdata/sdk-python-django/commit/b92ac6ffbeecf385e0b124dac24ea992bef97467))

## 1.0.6 - 2026-11-22

### Features

- Require internetdata 2.18.0: whether a bot uses an address, and whose ([`8048709`](https://github.com/internetdata/sdk-python-django/commit/8048709ffc40e0e36ab7852bcacb6381dabb88d0))

## 1.0.5 - 2026-11-20

### Features

- Require internetdata 2.17.0: a paid domain answer's hosting, co-hosted domains, home page, redirects and backlinks ([`5e225a9`](https://github.com/internetdata/sdk-python-django/commit/5e225a963108481398382ace9dbc9391c4fb2987))

## 1.0.4 - 2026-11-20

### Features

- Require internetdata 2.16.0: a tier, standing, license type, format or outcome the API adds reads as served ([`3502f2d`](https://github.com/internetdata/sdk-python-django/commit/3502f2da6db7da117e6d270e2a5998bee09ecaef))

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
