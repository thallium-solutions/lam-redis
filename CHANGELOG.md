# @lam/redis Changelog

All notable changes to `@lam/redis` are documented here.

## 2.0.0

### Changed

- Replaced expected service, transport, parse, timeout, cancellation,
  wrong-type, and closed-client panics with unsuffixed typed `Result[T]` APIs.
- Changed `connect` and `fromUrl` to return `Result[Redis]`, retain eager `PING`,
  and close failed clients before returning an error.
- Replaced missing-value sentinels in scalar, JSON, list, hash, sorted-set, TTL,
  and Pub/Sub reads with explicit `RedisNotFound`, `RedisTimeout`, or
  `RedisClosed` errors; `mget` now has ordered per-item results.
- Replaced pipeline command dictionaries and `"error: ..."` strings with
  `RedisCommand` and `Result[list[Result[any]]]`, preserving partial success and
  per-command failures.
- Added typed `RedisScanPage` and `RedisZMember` values, replaced `hsetMap` with
  an overloaded `hset`, and retained `any` only at genuinely heterogeneous
  Redis command/value boundaries.
- Replaced class `__init__` methods with `init`, removed avoidable raw Go from
  tests and value extraction, and made context unwrapping return errors rather
  than panic.
- Bumped the package major version to 2.0.0 and compiler compatibility to
  `lamc ^1.18`; updated the consumer runner and tests accordingly.

### Testing

- Added a service-backed installed-package scenario composing authenticated
  strings, JSON, collections, scans, pipelines, Pub/Sub, and typed failures.

## 1.0.0 - 2026-09-13

### Added

- Initial standalone `@lam/redis` package migrated from Lammergeier's
  `lamredis` standard-library module.
- Complete `Redis` API for health checks, generic commands, strings, native
  JSON, key lifecycle, counters, lists, hashes, sets, sorted sets, Pub/Sub,
  pipelines, scanning, and database test utilities.
- Complete blocking `PubSub` API with exact/pattern subscriptions, per-message
  timeouts, payload-only and metadata-bearing receives, and idempotent close.
- Lammergeier stdlib `lamcontext.Context.simple()` roots for client commands and
  derived `expirable` Pub/Sub wait scopes without changing the public API.
- Public scoped-package re-exports through `__init__.lam`.
- Consumer-style integration runner requiring `lamc >=1.16.0` and compiling
  both migrated Redis stdlib tests through `extlibs/@lam/redis`.
- Docker service script for no-auth Redis on port 6380 and password-protected
  Redis (`Password`) on port 6379, matching the language repository fixtures.
- Package metadata, pinned `github.com/redis/go-redis/v9 v9.19.0`, test/format/
  service scripts, comprehensive README, and Apache-2.0 license.
