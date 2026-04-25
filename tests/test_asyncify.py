import importlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

sys.path.insert(0, ".")

import autoasync._core as core
from autoasync import LazyProxy, autoasync, configure_autoasync, reset_autoasync


def process_sum(n):
    return sum(range(n))


@autoasync
def slow_add(a, b, delay=0.05):
    time.sleep(delay)
    return a + b


@pytest.fixture(autouse=True)
def reset_autoasync_state():
    reset_autoasync()
    yield
    reset_autoasync()


def test_returns_lazy_proxy():
    p = slow_add(1, 2, delay=1.0)
    assert isinstance(p, LazyProxy)


def test_correct_result():
    assert slow_add(3, 4) == 7


def test_concurrent():
    t0 = time.perf_counter()
    a = slow_add(1, 0, delay=0.3)
    b = slow_add(2, 0, delay=0.3)
    c = slow_add(3, 0, delay=0.3)
    assert a + b + c == 6
    assert time.perf_counter() - t0 < 0.6


def test_wrapped_callable():
    assert slow_add.__wrapped__(1, 2) == 3


def test_lazy_import():
    lazy_import = autoasync(importlib.import_module)
    json = lazy_import("json")
    re = lazy_import("re")
    assert json.dumps({"a": 1}) == '{"a": 1}'
    assert re.match(r"\d+", "42").group() == "42"


def test_use_process_top_level_function():
    wrapped = autoasync(use_process=True)(process_sum)
    assert wrapped(100) == 4950


def test_configure_thread_pool_size():
    configure_autoasync(thread_max_workers=3)

    @autoasync
    def identity(value):
        return value

    assert identity(7) == 7
    assert core._thread_pools[3]._max_workers == 3


def test_configure_process_pool_size():
    configure_autoasync(process_max_workers=2)
    wrapped = autoasync(use_process=True)(process_sum)
    assert wrapped(100) == 4950
    assert core._process_pools[2]._max_workers == 2


def test_same_thread_configuration_reuses_pool():
    configure_autoasync(thread_max_workers=3)

    @autoasync
    def first(value):
        return value

    @autoasync
    def second(value):
        return value + 1

    assert first(7) == 7
    pool = core._thread_pools[3]
    assert second(7) == 8
    assert core._thread_pools[3] is pool


def test_reconfigures_future_thread_pools_only():
    configure_autoasync(thread_max_workers=2)
    assert slow_add(1, 2) == 3
    original_pool = core._thread_pools[2]

    configure_autoasync(thread_max_workers=4)
    assert slow_add(2, 3) == 5

    assert core._thread_pools[2] is original_pool
    assert core._thread_pools[4]._max_workers == 4
    assert core._thread_pools[4] is not original_pool


def test_reset_autoasync_clears_configuration_and_cached_pools():
    configure_autoasync(thread_max_workers=2, process_max_workers=3)
    assert slow_add(1, 2) == 3
    assert autoasync(use_process=True)(process_sum)(100) == 4950

    reset_autoasync()

    assert core._thread_pool_max_workers is None
    assert core._process_pool_max_workers is None
    assert core._thread_pools == {}
    assert core._process_pools == {}

    assert slow_add(2, 3) == 5
    assert None in core._thread_pools


def test_use_process_rejects_nested_function():
    with pytest.raises(TypeError, match="module-level functions"):
        @autoasync(use_process=True)
        def compute(n):
            return sum(range(n))

        compute(100)


def test_use_process_rejects_non_process_executor():
    pool = ThreadPoolExecutor(max_workers=2)

    with pytest.raises(TypeError, match="ProcessPoolExecutor"):
        autoasync(use_process=True, executor=pool)(process_sum)


def test_custom_executor_ignores_global_configuration():
    configure_autoasync(thread_max_workers=1)
    pool = ThreadPoolExecutor(max_workers=2)

    @autoasync(executor=pool)
    def identity(value):
        return value

    assert identity(4) == 4
    assert core._thread_pools == {}


def test_removed_max_workers_argument_raises_type_error():
    with pytest.raises(TypeError, match="max_workers"):
        autoasync(max_workers=4)


def test_thread_max_workers_must_be_positive():
    with pytest.raises(ValueError, match="thread_max_workers"):
        configure_autoasync(thread_max_workers=0)


def test_process_max_workers_must_be_positive():
    with pytest.raises(ValueError, match="process_max_workers"):
        configure_autoasync(process_max_workers=False)


def test_no_args_decorator():
    @autoasync()
    def slow(x):
        return x * 2

    assert slow(5) == 10


def test_recursive_fib():
    @autoasync
    def fib(n):
        if n <= 1:
            return n
        return fib(n - 1) + fib(n - 2)

    assert fib(10) == 55
    assert fib(15) == 610


def test_recursive_small_pool():
    pool = ThreadPoolExecutor(max_workers=2)

    @autoasync(executor=pool)
    def fib(n):
        if n <= 1:
            return n
        return fib(n - 1) + fib(n - 2)

    assert fib(10) == 55


def test_mutual_recursion():
    @autoasync
    def is_even(n):
        if n == 0:
            return True
        return is_odd(n - 1)

    @autoasync
    def is_odd(n):
        if n == 0:
            return False
        return is_even(n - 1)

    assert bool(is_even(10)) is True
    assert bool(is_odd(7)) is True
