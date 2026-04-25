"""Core implementation for `autoasync`."""

import asyncio
import functools
import inspect
import threading
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

from autoasync._proxy import LazyProxy

__all__ = ["autoasync", "configure_autoasync", "reset_autoasync", "run_sync"]

F = TypeVar("F", bound=Callable[..., Any])
_UNSET = object()

_thread_pools: Dict[Optional[int], ThreadPoolExecutor] = {}
_process_pools: Dict[Optional[int], ProcessPoolExecutor] = {}
_thread_pool_max_workers: Optional[int] = None
_process_pool_max_workers: Optional[int] = None
_pool_lock = threading.Lock()
_worker_local = threading.local()


def _get_thread_pool() -> ThreadPoolExecutor:
    with _pool_lock:
        max_workers = _thread_pool_max_workers
        pool = _thread_pools.get(max_workers)
        if pool is None:
            pool = ThreadPoolExecutor(max_workers=max_workers)
            _thread_pools[max_workers] = pool
        return pool


def _get_process_pool() -> ProcessPoolExecutor:
    with _pool_lock:
        max_workers = _process_pool_max_workers
        pool = _process_pools.get(max_workers)
        if pool is None:
            pool = ProcessPoolExecutor(max_workers=max_workers)
            _process_pools[max_workers] = pool
        return pool


def _is_worker_thread() -> bool:
    """Return whether the current thread is already executing autoasync work."""
    return getattr(_worker_local, "active", False)


def _run_as_worker(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run a callable while marking the current thread as an autoasync worker."""
    previous = getattr(_worker_local, "active", False)
    _worker_local.active = True
    try:
        return fn(*args, **kwargs)
    finally:
        _worker_local.active = previous


def _validate_worker_count(name: str, max_workers: Optional[int]) -> None:
    """Validate the configured pool size for built-in executors."""
    if max_workers is None:
        return

    if isinstance(max_workers, bool) or not isinstance(max_workers, int) or max_workers <= 0:
        raise ValueError(f"`{name}` must be a positive integer or `None`.")


def configure_autoasync(
    *,
    thread_max_workers=_UNSET,
    process_max_workers=_UNSET,
) -> None:
    """Configure default sizes for built-in thread and process pools."""
    global _thread_pool_max_workers, _process_pool_max_workers

    if thread_max_workers is not _UNSET:
        _validate_worker_count("thread_max_workers", thread_max_workers)
    if process_max_workers is not _UNSET:
        _validate_worker_count("process_max_workers", process_max_workers)

    with _pool_lock:
        if thread_max_workers is not _UNSET:
            _thread_pool_max_workers = thread_max_workers
        if process_max_workers is not _UNSET:
            _process_pool_max_workers = process_max_workers


def reset_autoasync() -> None:
    """Reset built-in executor configuration and cached pools."""
    global _thread_pool_max_workers, _process_pool_max_workers

    with _pool_lock:
        thread_pools = list(_thread_pools.values())
        process_pools = list(_process_pools.values())
        _thread_pools.clear()
        _process_pools.clear()
        _thread_pool_max_workers = None
        _process_pool_max_workers = None

    for pool in thread_pools:
        pool.shutdown(wait=False)
    for pool in process_pools:
        pool.shutdown(wait=True)


def _validate_process_target(fn: Callable[..., Any]) -> Tuple[str, str]:
    """Validate that a callable is safe to resolve in a worker process."""
    raw_fn = inspect.unwrap(fn)

    if not inspect.isfunction(raw_fn):
        raise TypeError(
            "`use_process=True` only supports importable module-level functions; "
            f"got callable type `{type(raw_fn).__name__}`."
        )

    module_name = raw_fn.__module__
    function_name = raw_fn.__name__
    qualname = raw_fn.__qualname__

    if module_name == "__main__":
        raise TypeError(
            "`use_process=True` only supports functions from importable modules. "
            f"`{qualname}` is defined in `__main__`; move it to a module or use thread mode."
        )

    if "<locals>" in qualname or qualname != function_name or function_name == "<lambda>":
        raise TypeError(
            "`use_process=True` only supports importable module-level functions; "
            f"got `{module_name}.{qualname}`. Define the function at module scope or use thread mode."
        )

    return module_name, function_name


def _call_in_process(
    module_name: str,
    function_name: str,
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
) -> Any:
    """Import a module-level function by name and execute it inside a worker process."""
    import importlib

    module = importlib.import_module(module_name)
    try:
        obj = getattr(module, function_name)
    except AttributeError as exc:
        raise TypeError(
            "`use_process=True` requires the target to remain available as a "
            f"module-level attribute, but `{module_name}.{function_name}` could not be imported."
        ) from exc

    fn = inspect.unwrap(obj)
    return fn(*args, **kwargs)


def autoasync(
    func=None,
    *,
    executor=None,
    use_process: bool = False,
):
    """Wrap a callable so it returns a LazyProxy immediately."""

    if use_process and executor is not None and not isinstance(executor, ProcessPoolExecutor):
        raise TypeError(
            "`use_process=True` requires a `ProcessPoolExecutor` or no explicit `executor`."
        )

    def decorator(fn: F) -> F:
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                if _is_worker_thread():
                    return asyncio.run(fn(*args, **kwargs))

                fut: Future = Future()

                def run() -> None:
                    try:
                        result = _run_as_worker(asyncio.run, fn(*args, **kwargs))
                        fut.set_result(result)
                    except Exception as exc:
                        fut.set_exception(exc)

                _get_thread_pool().submit(run)
                return LazyProxy(fut)

        else:
            uses_process_pool = use_process or isinstance(executor, ProcessPoolExecutor)
            process_target = _validate_process_target(fn) if uses_process_pool else None

            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                if _is_worker_thread():
                    return fn(*args, **kwargs)

                if process_target is not None:
                    module_name, function_name = process_target
                    process_executor = executor if executor is not None else _get_process_pool()
                    bound = functools.partial(
                        _call_in_process,
                        module_name,
                        function_name,
                        args,
                        kwargs,
                    )
                    return LazyProxy(process_executor.submit(bound))

                thread_executor = executor if executor is not None else _get_thread_pool()

                def task():
                    return _run_as_worker(fn, *args, **kwargs)

                return LazyProxy(thread_executor.submit(task))

        wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
        return wrapper

    return decorator(func) if func is not None else decorator


def run_sync(coro):
    """Run a coroutine from synchronous code."""
    return asyncio.run(coro)
