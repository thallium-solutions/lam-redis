# @lam/redis Changelog

All notable changes to `@lam/redis` are documented here.

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
