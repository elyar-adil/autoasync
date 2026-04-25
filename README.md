# autoasync

Start synchronous work in the background and get a proxy back immediately.  
The call only blocks when you actually use the result.

```python
from pathlib import Path
from tempfile import gettempdir
from typing import Optional
from urllib.parse import urlparse
from urllib.request import urlopen

from autoasync import autoasync


@autoasync
def download(url: str) -> Optional[Path]:
    name = Path(urlparse(url).path).name or "download.bin"
    destination = Path(gettempdir()) / name

    try:
        with urlopen(url, timeout=10) as response:
            destination.write_bytes(response.read())
    except Exception:
        return None

    return destination


file_path = download("https://example.com/data.txt")
prepare_page()

if file_path:
    with open(file_path, "rb") as fh:
        print(fh.read(32))
```

`if file_path:` resolves the proxy and handles the `None` case.  
`open(file_path)` works because `LazyProxy` implements `__fspath__` when the result is path-like.

## Why use it?

`autoasync` is for retrofitting concurrency into an existing synchronous codebase:

- no async contagion through the whole call chain
- minimal changes: `@autoasync` or `autoasync(fn)` is usually enough
- deferred waiting: work starts now, blocking happens only when the value is used
- easy incremental speedups for I/O-heavy sync code

It is not a replacement for native `async` / `await` in large async systems.  
It is a small tool for hiding latency in otherwise synchronous code.

## Install

```bash
pip install autoasync
```

## More examples

### Fan out several calls concurrently

```python
from autoasync import autoasync


@autoasync
def fetch(url: str) -> str:
    import urllib.request
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.read().decode()


a = fetch("https://example.com/a")
b = fetch("https://example.com/b")
c = fetch("https://example.com/c")

combined = a + "\n" + b + "\n" + c
```

### CPU-bound work with processes

`use_process=True` only supports importable module-level functions.

```python
from autoasync import autoasync


@autoasync(use_process=True)
def crunch(n: int) -> int:
    return sum(range(n))


result = crunch(10_000_000)
do_other_work()
print(result)
```

## Configuration

Use `configure_autoasync(...)` when you want to keep the library-managed executors but control their default sizes.

```python
from autoasync import configure_autoasync

configure_autoasync(thread_max_workers=8, process_max_workers=4)
```

If you pass `executor=...`, that custom executor is used instead of the built-in pools.  
Use `reset_autoasync()` to clear cached built-in pools and restore default configuration, especially in tests.

## What the proxy supports

The returned value behaves like the eventual result for most common Python protocols, including:

- attribute access
- arithmetic and comparisons
- container access and iteration
- conversions such as `int`, `float`, `str`, `bytes`, and `bool`
- `await proxy` inside async code
- context managers
- `open(proxy)` and other path-like usage through `__fspath__`

The background result is resolved once and then cached.

## Important behavior

### `is` is special

`is` checks object identity and cannot be overloaded in Python:

```python
from autoasync import autoasync


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
from autoasync import autoasync


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

Unsupported targets raise a clear `TypeError`.

## Requirements

- Python 3.8+
- No runtime dependencies

## License

MIT
