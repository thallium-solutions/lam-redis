# @lam/redis

`@lam/redis` is the Redis client package for the
[Lammergeier programming language](https://github.com/thallium-solutions/lammergeier-lang).
It preserves the `Redis` and `PubSub` APIs formerly provided by the
`lamredis` standard-library module and is backed by the official
[`github.com/redis/go-redis/v9`](https://github.com/redis/go-redis) client.

Use it for caches, counters, queues, hashes, membership indexes, leaderboards,
Redis Pub/Sub, batched commands, native JSON values, and commands not yet
covered by a typed helper. `go-redis` supplies connection pooling, transparent
reconnects, ACL authentication, and transport behavior.

## Requirements

- `lamc` **1.16.0 or newer** within the compatible `1.x` line (`^1.16`).
- Go capable of building `github.com/redis/go-redis/v9 v9.19.0`.
- A Redis-compatible server for integration tests and runtime use.

## Installation

Install from the registry after release:

```bash
lamc install @lam/redis@1.0.0
```

Install directly from Git:

```bash
lamc install https://github.com/thallium-solutions/lam-redis.git
```

Or install a local checkout while developing:

```bash
lamc install /path/to/lam-redis
```

All forms expose the same scoped import:

```lammergeier
from @lam/redis import PubSub, Redis
```

## Connecting and configuration

`Redis.connect` accepts an address, password, logical database, and Redis 6+
ACL username. It performs `PING` before returning, so a bad address or bad
credentials fail at connection time rather than on the first application
command.

```lammergeier
from @lam/redis import Redis

# No authentication, database 0.
local: Redis = Redis.connect("localhost:6380")

# Password authentication and a selected logical database.
cache: Redis = Redis.connect(
    "localhost:6379",
    password="Password",
    db=1,
)

# ACL username plus password.
acl: Redis = Redis.connect(
    "redis.internal:6379",
    password="secret",
    db=0,
    username="application",
)
```

`Redis.fromUrl` accepts `redis://` and TLS-enabled `rediss://` URLs using
`go-redis` URL parsing:

```lammergeier
from @lam/redis import Redis
from lamenv import Env

redis: Redis = Redis.fromUrl(Env.get("REDIS_URL"))
```

A client is safe for concurrent use because each command uses the `go-redis`
connection pool. Reuse clients instead of constructing one per command, and
call `close()` during shutdown. `close()` is idempotent; the client must not be
used afterwards.

## Quick start

```lammergeier
from @lam/redis import Redis

func main() {
    redis: Redis = Redis.connect("localhost:6379", password="Password")

    redis.set("greeting", "hello", ttlSec=60)
    print(redis.get("greeting"))

    redis.rpush("jobs", ["resize:1", "email:2"])
    print(redis.lpop("jobs"))

    redis.hsetMap("user:42", {"name": "Ada", "tier": "gold"})
    print(redis.hgetAll("user:42")["name"])

    redis.close()
}
```

## Data structures and commands

### Strings, JSON, and key lifecycle

| Method | Behavior |
|---|---|
| `set(key, value, ttlSec=0)` | Store a stringified value; positive TTL is applied atomically. |
| `setNx(key, value, ttlSec=0)` | Set only when absent and report whether the write occurred. |
| `get(key)` | Read a string; missing keys return `""`. |
| `getDel(key)` | Atomically read and delete; missing keys return `""`. |
| `mset(pairs)` / `mget(keys)` | Set or fetch multiple values in one round trip. |
| `setJson(key, value, ttlSec=0)` | Encode and store a native Lam `json` value. |
| `getJson(key)` | Decode native `json`; a missing key becomes JSON `null`. |
| `exists(keys)` / `delete(keys)` | Return the number of existing or deleted keys. |
| `expire(key, ttlSec)` / `persist(key)` | Add or remove expiration and report whether Redis changed the key. |
| `ttl(key)` | Seconds remaining; `-1` means persistent and `-2` means missing. |
| `type_(key)` | Redis type name, or `"none"` for a missing key. |
| `keys(pattern)` | Blocking keyspace glob; avoid on large production databases. |
| `scan(cursor, match="", count=0)` | Cursor-safe iteration returning `{"cursor": int, "keys": list[str]}`. |

Values accepted as `any` are converted consistently: strings remain strings,
byte slices become text, booleans become `"1"`/`"0"`, numbers use their text
representation, and `None` becomes the empty string.

Use `exists([key])` when an empty value must be distinguished from a missing
key. `mget` preserves input order and represents each missing entry as `""`.

### Counters

| Method | Return |
|---|---|
| `incr(key)` / `decr(key)` | New integer value after changing by one. |
| `incrBy(key, by)` / `decrBy(key, by)` | New integer value after changing by `by`. |

Redis applies its normal integer validation and atomicity guarantees.

### Lists

```lammergeier
redis.rpush("queue", ["a", "b", "c"])
first: str = redis.lpop("queue")
remaining: list[str] = redis.lrange("queue", 0, -1)
```

- `lpush(key, values)` and `rpush(key, values)` return the new list length.
- `lpop(key)` and `rpop(key)` return `""` when the list/key is empty.
- `llen(key)` returns the list length.
- `lrange(key, start, stop)` uses Redis's inclusive indexes; `-1` is the end.

### Hashes

```lammergeier
redis.hset("user:1", "name", "Ada")
redis.hsetMap("user:1", {"tier": "gold", "score": 5})
profile: dict[str, str] = redis.hgetAll("user:1")
```

- `hset` and `hsetMap` return the number of newly-added fields.
- `hget` returns `""` for a missing field.
- `hgetAll` returns `dict[str, str]`.
- `hdel` returns the number of fields removed.
- `hexists`, `hkeys`, and `hincrBy` expose membership, field listing, and
  atomic integer updates.

### Sets

- `sadd(key, members)` and `srem(key, members)` return the number changed.
- `smembers(key)` returns all members without ordering guarantees.
- `sismember(key, member)` tests membership.
- `scard(key)` returns cardinality.

### Sorted sets

```lammergeier
redis.zadd("scores", 100.0, "alice")
redis.zincrBy("scores", 5.0, "alice")
ranked: list[dict[str, any]] = redis.zrangeWithScores("scores", 0, -1)
```

- `zadd` returns the number of newly-added members.
- `zincrBy` returns the new floating-point score.
- `zscore` returns `0.0` for a missing member.
- `zrange` returns only members.
- `zrangeWithScores` returns rows containing `member` and `score`.
- `zrem` returns the number removed; `zcard` returns cardinality.

### Pub/Sub

```lammergeier
from @lam/redis import PubSub, Redis

subscriber: Redis = Redis.connect("localhost:6379", password="Password")
publisher: Redis = Redis.connect("localhost:6379", password="Password")

messages: PubSub = subscriber.subscribe(["events"])
messages.setTimeout(3000)
publisher.publish("events", "ready")
print(messages.next())

messages.close()
publisher.close()
subscriber.close()
```

- `publish(channel, message)` returns the receiving subscriber count.
- `subscribe(channels)` listens to exact channels.
- `psubscribe(patterns)` listens to Redis glob patterns.
- `PubSub.next()` blocks and returns only the payload.
- `PubSub.nextWith()` returns `channel`, `pattern`, and `payload`.
- `setTimeout(ms)` applies per wait; `0` waits indefinitely.
- `next` returns `""`, and `nextWith` returns an empty/nil-backed dictionary,
  after timeout, closure, cancellation, or receive failure.
- Always call `PubSub.close()` to release its dedicated connection.

Subscription setup waits for Redis's confirmation before returning, preventing
an immediate publisher from racing the `SUBSCRIBE` command.

### Pipelines

```lammergeier
commands: list[dict[str, any]] = [
    {"cmd": "GET", "args": ["greeting"]},
    {"cmd": "INCR", "args": ["hits"]},
]
results: list[any] = redis.pipeline(commands)
```

Commands are sent in one network round trip and results preserve input order.
An individual command failure is represented as a string beginning with
`"error: "`; it does not discard successful results from the same pipeline.

### Generic commands and maintenance

- `exec(cmd, args)` is the escape hatch for commands without typed wrappers.
  Its return type follows `go-redis`: scalar, integer, list, map, or `None`.
- `ping()` returns `"PONG"` on a healthy server.
- `dbSize()` returns the selected database's key count.
- `flushDb()` deletes every key in the selected database. It is intended for
  isolated tests, not shared or production Redis deployments.

## Result and failure behavior

Version 1.0.0 intentionally preserves the former stdlib API. Command methods do
**not** return `lamerrors.Result` values:

- Network, authentication, server, wrong-type, invalid JSON, and command errors
  panic with a message prefixed by `redis:`.
- `connect` and `fromUrl` eagerly call `PING`, so malformed URLs, unavailable
  servers, and rejected credentials fail before a client is returned.
- Missing values are ordinary sentinels rather than failures: `""` for string,
  hash, and list reads; `0.0` for `zscore`; JSON `null` for `getJson`; and the
  documented Redis TTL/type values.
- Pub/Sub receive timeout/close/cancellation is reduced to an empty return, as
  documented above.
- Pipeline item failures are `"error: ..."` strings in the result list.
- `close()` ignores the underlying close error and is safe to call repeatedly.

Because missing strings and empty strings have the same return value, call
`exists`; because missing sorted-set members and a score of zero have the same
return value, use `exec("ZSCORE", ...)` when that distinction is required.

## Context handling

Every `Redis` owns one simple `Context`; every `PubSub` inherits its
client's context, and timed message waits derive expirable child contexts.
The package uses the Lammergeier standard library's `lamcontext.Context` for
client roots, Pub/Sub child scopes, cancellation, and per-wait expiration. One
small Go interop helper unwraps `Context.native()` for `go-redis`, so command
wrappers do not duplicate `context.Background()` or `context.WithTimeout()`
logic. This keeps the public `Redis`/`PubSub` signatures unchanged while making
context ownership explicit.

## Service-backed tests

The two migrated stdlib integration tests are compiled as real package
consumers: the Python runner creates a temporary `extlibs/@lam/redis` link and
builds each test outside this checkout. It rejects `lamc` older than 1.16.0.

Start the package-local Docker services in one terminal:

```bash
lamc lib run service
# equivalent: sh test-services.sh
```

The ports and credentials intentionally match the main Lammergeier language
service script:

| Address | Authentication |
|---|---|
| `localhost:6380` | none |
| `localhost:6379` | password `Password` |

Then run the integration tests in another terminal:

```bash
lamc lib run test
```

Useful direct runner options:

```bash
python3 tests/run_lamredis_tests.py --compile-only --verbose
python3 tests/run_lamredis_tests.py --race --verbose
```

`--compile-only` validates scoped resolution and Go compilation when Docker or
Redis is unavailable. The service script stops only containers it started;
pre-existing running containers with its expected names are left untouched.

## Formatting

```bash
lamc lib run format
```

## License

Apache License 2.0. See [LICENSE](LICENSE).
