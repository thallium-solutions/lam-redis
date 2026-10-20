# @lam/redis

`@lam/redis` is the Result-first Redis client package for the
[Lammergeier programming language](https://github.com/thallium-solutions/lammergeier-lang).
It wraps `github.com/redis/go-redis/v9` v9.19.0 and provides strings, native
JSON, key lifecycle, collections, Pub/Sub, typed scan/sorted-set values,
pipelines, and an arbitrary-command escape hatch.

Version 2 is a breaking release. Expected service, transport, parse, timeout,
wrong-type, and closed-client failures now use unsuffixed `Result[T]` methods
rather than panic or sentinel values.

## Requirements and installation

- `lamc` 1.18.0 or newer including 2.x (`>=1.18, <4`).
- Go capable of building `github.com/redis/go-redis/v9 v9.19.0`.
- A Redis-compatible server for runtime use and integration tests.

```bash
lamc install @lam/redis@2.0.0
# or
lamc install https://github.com/thallium-solutions/lam-redis.git
```

```lammergeier
from @lam/redis import PubSub, Redis, RedisCommand, RedisScanPage, RedisZMember
from lamerrors import Result
```

## Connecting

`connect` and `fromUrl` return `Result[Redis]` and eagerly run `PING`, so bad
addresses, credentials, and URL configuration fail before a client is returned.

```lammergeier
func openCache() -> Result[Redis] {
    return Redis.connect(
        "localhost:6379",
        password="Password",
        db=1,
        username="",
    )
}

cache: Redis = Redis.fromUrl("redis://:Password@localhost:6379/1")?
```

Clients are safe for concurrent use through the go-redis pool. Reuse them and
handle `close()` during shutdown. Close is idempotent and returns `Result[any]`.

## Quick start

```lammergeier
func cacheExample() -> Result[bool] {
    redis: Redis = Redis.connect("localhost:6379", password="Password")?
    _ = redis.set("greeting", "hello", ttlSec=60)?
    greeting: str = redis.get("greeting")?
    print(greeting)

    _ = redis.rpush("jobs", ["resize:1", "email:2"])?
    first: str = redis.lpop("jobs")?
    print(first)

    _ = redis.hset("user:42", {"name": "Ada", "tier": "gold"})?
    profile: dict[str, str] = redis.hgetAll("user:42")?
    print(profile["name"])

    _ = redis.close()?
    return Result.Ok(true)
}
```

## Failure and absence semantics

- Service, transport, wrong-type, invalid JSON, context, and closed-client
  failures return `RedisError`.
- Missing scalar reads return `RedisNotFound`: `get`, `getDel`, `getJson`,
  `lpop`, `rpop`, `hget`, and `zscore`. Stored empty strings, JSON null, and a
  sorted-set score of zero therefore remain distinguishable from absence.
- `ttl` returns `RedisNotFound` for a missing key and `Ok(-1)` for a persistent
  key. Redis's explicit `TYPE` response remains `Ok("none")` for a missing key.
- `mget` returns `Result[list[Result[str]]]`: the outer result describes the
  command, and each ordered inner result distinguishes a value from a missing
  key.
- Pub/Sub timeout, cancellation, closure, and receive failure are errors rather
  than empty payload/dictionary sentinels.
- Invalid local arguments return `RedisArgumentError`.

## Typed API map

Every method below that reaches Redis returns `Result`.

### Connection, generic commands, and lifecycle

| API | Return |
|---|---|
| `Redis.connect(addr, password="", db=0, username="")` | `Result[Redis]` |
| `Redis.fromUrl(url)` | `Result[Redis]` |
| `ping()` | `Result[str]` |
| `exec(command, args=[])` | `Result[any]` |
| `dbSize()` | `Result[int]` |
| `flushDb()` | `Result[bool]` |
| `close()` | `Result[any]` |

`any` is intentionally retained only where the Redis protocol is genuinely
heterogeneous: arbitrary command arguments/results and values that Redis
stringifies.

### Strings, JSON, and keys

| API | Return |
|---|---|
| `set(key, value, ttlSec=0)` | `Result[bool]` |
| `setNx(key, value, ttlSec=0)` | `Result[bool]` |
| `get(key)` / `getDel(key)` | `Result[str]` |
| `setJson(key, value, ttlSec=0)` | `Result[bool]` |
| `getJson(key)` | `Result[json]` |
| `mset(pairs)` | `Result[bool]` |
| `mget(keys: list[str])` | `Result[list[Result[str]]]` |
| `exists(keys)` / `delete(keys)` | `Result[int]` |
| `expire(key, ttlSec)` / `persist(key)` | `Result[bool]` |
| `ttl(key)` | `Result[int]` |
| `type_(key)` | `Result[str]` |
| `keys(pattern)` | `Result[list[str]]` |
| `scan(cursor, match="", count=0)` | `Result[RedisScanPage]` |

`RedisScanPage` exposes typed `cursor: int` and `keys: list[str]` fields instead
of a `dict[str, any]`.

### Counters and collections

| Group | APIs and return values |
|---|---|
| Counters | `incr`, `incrBy`, `decr`, `decrBy` -> `Result[int]` |
| Lists | `lpush`, `rpush`, `llen` -> `Result[int]`; `lpop`, `rpop` -> `Result[str]`; `lrange` -> `Result[list[str]]` |
| Hashes | overloaded `hset(key, field, value)` and `hset(key, fields)` -> `Result[int]`; `hget` -> `Result[str]`; `hgetAll` -> `Result[dict[str, str]]`; `hdel`, `hincrBy` -> `Result[int]`; `hexists` -> `Result[bool]`; `hkeys` -> `Result[list[str]]` |
| Sets | `sadd`, `srem`, `scard` -> `Result[int]`; `smembers` -> `Result[list[str]]`; `sismember` -> `Result[bool]` |
| Sorted sets | `zadd`, `zrem`, `zcard` -> `Result[int]`; `zincrBy`, `zscore` -> `Result[float]`; `zrange` -> `Result[list[str]]`; `zrangeWithScores` -> `Result[list[RedisZMember]]` |

`RedisZMember` exposes `member: str` and `score: float`, eliminating the former
`dict[str, any]` rows. `hsetMap` was replaced by the map overload of `hset`.

## Pub/Sub

```lammergeier
subscriber: Redis = Redis.connect("localhost:6379", password="Password")?
publisher: Redis = Redis.connect("localhost:6379", password="Password")?

messages: PubSub = subscriber.subscribe(["events"])?
_ = messages.setTimeout(3000)?
_ = publisher.publish("events", "ready")?
payload: str = messages.next()?

_ = messages.close()?
_ = publisher.close()?
_ = subscriber.close()?
```

| API | Return |
|---|---|
| `publish(channel, message)` | `Result[int]` subscriber count |
| `subscribe(channels)` / `psubscribe(patterns)` | `Result[PubSub]` after server confirmation |
| `PubSub.setTimeout(ms)` | `Result[bool]` |
| `PubSub.next()` | `Result[str]` |
| `PubSub.nextWith()` | `Result[dict[str, str]]` |
| `PubSub.close()` | `Result[any]` |

## Pipelines

Pipelines use typed commands and nested results instead of command dictionaries
and error strings:

```lammergeier
commands: list[RedisCommand] = [
    RedisCommand("GET", ["greeting"]),
    RedisCommand("INCR", ["hits"]),
]
results: list[Result[any]] = redis.pipeline(commands)?

value: str = results[0]?
newCount: int = results[1]?
```

`pipeline(commands)` returns `Result[list[Result[any]]]`. The outer result
reports invalid input or unavailable pipeline/client state. Ordered inner
results preserve each command's success, Redis error, transport failure, or
`RedisNotFound`; partial successes are never discarded and errors are never
encoded as strings.

## Context handling and Go boundary

Each `Redis` owns a `lamcontext.Context`; subscriptions derive children and
timed receives derive expirable contexts. Version 2 uses the fallible Lam 1.18
`Context.expirable` API. Raw Go is limited to unwrapping the native context and
calling go-redis. Result propagation, typed scan/zset access, command creation,
and test usage remain in Lam.

## Testing

```bash
# Offline/compiler gate; never contacts Redis.
python3 tests/run_lamredis_tests.py --compile-only --verbose

# Service-backed run only when the fixture already exists.
python3 tests/run_lamredis_tests.py --verbose
```

The integration runner expects password-protected Redis at `localhost:6379`
with password `Password`. Tests call `FLUSHDB`; never point them at shared or
production data. `test-services.sh` is available for explicit local fixture
management, but automated verification should not start external or destructive
services implicitly.

Format sources with `lamc fmt .`.

## License

Apache License 2.0. See [LICENSE](LICENSE). Release notes are in
[CHANGELOG.md](CHANGELOG.md).
