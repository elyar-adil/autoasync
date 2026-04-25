# autoasync

Wrap synchronous work so it starts in the background and returns immediately.  
The call only blocks when you actually use the result.

```python
from autoasync import autoasync


def load_report(path):
    ...


load_report_async = autoasync(load_report)
report = load_report_async("report.csv")

prepare_page()                    # runs while load_report works in background
print(report)                     # blocks here only if the result is not ready yet
```

## Why use this instead of `async` / `await`?

`autoasync` is mainly for **retrofitting concurrency into existing synchronous code**.
Compared with Python's built-in `async` / `await`, its main advantages are:

- **No async contagion**: callers can stay synchronous, so you do not need to turn the whole call chain into `async def` just to overlap one slow step.
- **Minimal code changes**: wrapping a function with `@autoasync` or `autoasync(fn)` is often enough to start work in the background.
- **Deferred waiting**: you do not have to decide upfront where to `await`; execution only blocks when the value is actually needed.
- **Easy incremental optimization**: this is convenient when improving a mature sync codebase, because you can add concurrency without redesigning APIs around an event loop.

That trade-off is intentional: this abstraction adds overhead, so it is not a replacement for native `async` / `await` in high-throughput async systems. It is most useful when you want a simple, low-friction way to hide latency in otherwise synchronous code.

## Install

```bash
pip install autoasync
```

## Usage

### Decorate any synchronous function

```python
from autoasync import autoasync


@autoasync
def fetch(url: str) -> str:
    import requests
    return requests.get(url).text


result = fetch("https://example.com")
do_other_work()
print(result)
```

### Run several calls concurrently

```python
a = fetch("https://example.com/a")
b = fetch("https://example.com/b")
c = fetch("https://example.com/c")

combined = a + "\n" + b + "\n" + c
```

### CPU-bound work with processes

`use_process=True` is only supported for importable module-level functions.

```python
from autoasync import autoasync


@autoasync(use_process=True)
def crunch(n: int) -> int:
    return sum(range(n))


result = crunch(10_000_000)
do_other_work()
print(result)
```

### Custom executor

```python
from concurrent.futures import ThreadPoolExecutor
from autoasync import autoasync

pool = ThreadPoolExecutor(max_workers=4)


@autoasync(executor=pool)
def read(path: str) -> str:
    with open(path) as f:
        return f.read()
```

### Configure built-in executors globally

Use `configure_autoasync(...)` when you want to keep the library-managed executors but control their default sizes.

```python
from autoasync import autoasync, configure_autoasync

configure_autoasync(thread_max_workers=8, process_max_workers=4)

@autoasync
def fetch(url):
    ...


@autoasync(use_process=True)
def crunch(n):
    return sum(range(n))


page = fetch("https://example.com")   # uses the configured thread pool
total = crunch(10_000_000)            # uses the configured process pool
```

Configuration changes apply to future built-in pools only. Existing cached pools are not replaced.
If you pass a custom `executor`, the global built-in pool configuration is ignored.

Use `reset_autoasync()` to clear cached built-in pools and restore default configuration, which is especially useful in tests.

### Access the original function

```python
@autoasync
def add(a, b):
    return a + b


add.__wrapped__(1, 2)
```

## What the returned value supports

The returned value behaves like the final result for most common Python protocols, including:

- attribute access
- arithmetic and comparisons
- container access and iteration
- conversions such as `int`, `float`, `str`, `bytes`, and `bool`
- context managers
- `open()` path usage through `__fspath__`

The background result is resolved once and then cached.

## Important behavior

### `is` is special

`is` checks object identity and cannot be overloaded in Python. That means:

```python
resolve_true = autoasync(lambda: True)
result = resolve_true()

result == True         # works
bool(result) is True   # works
result is True         # False: `is` checks identity, not the eventual value
```

If you need identity-style checks, resolve first or use `==` / `bool(...)`.

### Exceptions are deferred

If the wrapped function raises an exception, the exception is not raised at call time.  
It is re-raised when the result is first needed.

```python
@autoasync
def explode():
    raise RuntimeError("boom")


result = explode()     # no exception yet
print(result)          # raises RuntimeError here
```

### Process mode restrictions

When `use_process=True`, the wrapped function must be:

- defined at module scope
- importable from its module
- a normal function, not a lambda, nested function, bound method, or callable object
- optionally paired with `configure_autoasync(process_max_workers=...)` to size the built-in process pool

Unsupported targets raise a clear `TypeError`.

## How it works

```python
result = slow_fn(arg)          # submits fn(arg) to an executor
                               # returns immediately

do_other_work()                # runs concurrently with fn(arg)

print(result + 1)              # blocks only here if needed
```

## Requirements

- Python 3.8+
- No runtime dependencies

## License

MIT
