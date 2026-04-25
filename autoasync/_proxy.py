"""
LazyProxy — 透明代理一个尚未完成的后台任务结果。
访问任意属性/运算/转换时，自动阻塞等待结果就绪（仅一次）。
"""

import asyncio
import math
import operator
from concurrent.futures import Future
from typing import Any, Iterator

_MISSING = object()


class LazyProxy:
    """
    透明代理一个 concurrent.futures.Future 的结果。

    - 任意属性访问、运算符、类型转换均会触发等待
    - 结果缓存后，后续访问零开销
    - 通过 __wrapped_future__ 可拿到原始 Future
    """

    __slots__ = ("__wrapped_future__", "_lp_cache")

    def __init__(self, future: Future) -> None:
        object.__setattr__(self, "__wrapped_future__", future)
        object.__setattr__(self, "_lp_cache", _MISSING)

    # ── 唯一阻塞点 ────────────────────────────────────────────────────────────

    def _resolve(self) -> Any:
        cache = object.__getattribute__(self, "_lp_cache")
        if cache is _MISSING:
            fut: Future = object.__getattribute__(self, "__wrapped_future__")
            result = fut.result()
            object.__setattr__(self, "_lp_cache", result)
            return result
        return cache

    # ── 属性访问 ──────────────────────────────────────────────────────────────

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resolve(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._resolve(), name, value)

    def __delattr__(self, name: str) -> None:
        delattr(self._resolve(), name)

    def __dir__(self):
        return dir(self._resolve())

    # ── 类型透传 ──────────────────────────────────────────────────────────────

    @property
    def __class__(self):  # type: ignore[override]
        try:
            return type(self._resolve())
        except Exception:
            return type(self)

    # ── 字符串 / 表示 ─────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        cache = object.__getattribute__(self, "_lp_cache")
        if cache is not _MISSING:
            return repr(cache)
        fut: Future = object.__getattribute__(self, "__wrapped_future__")
        if fut.done():
            return repr(self._resolve())
        return "<LazyProxy [pending]>"

    def __str__(self) -> str:       return str(self._resolve())
    def __bytes__(self) -> bytes:   return bytes(self._resolve())
    def __format__(self, spec: str) -> str: return format(self._resolve(), spec)

    # ── 数值转换 ──────────────────────────────────────────────────────────────

    def __bool__(self) -> bool:     return bool(self._resolve())
    def __int__(self) -> int:       return int(self._resolve())
    def __float__(self) -> float:   return float(self._resolve())
    def __complex__(self):          return complex(self._resolve())
    def __index__(self) -> int:     return operator.index(self._resolve())

    def __round__(self, n=None):
        return round(self._resolve(), n) if n is not None else round(self._resolve())

    def __trunc__(self):            return math.trunc(self._resolve())
    def __floor__(self):            return math.floor(self._resolve())
    def __ceil__(self):             return math.ceil(self._resolve())

    # ── 一元运算 ──────────────────────────────────────────────────────────────

    def __abs__(self):              return abs(self._resolve())
    def __neg__(self):              return -self._resolve()
    def __pos__(self):              return +self._resolve()
    def __invert__(self):           return ~self._resolve()

    # ── 算术运算 ──────────────────────────────────────────────────────────────

    def __add__(self, o):           return self._resolve() + o
    def __radd__(self, o):          return o + self._resolve()
    def __iadd__(self, o):          return self._resolve() + o
    def __sub__(self, o):           return self._resolve() - o
    def __rsub__(self, o):          return o - self._resolve()
    def __isub__(self, o):          return self._resolve() - o
    def __mul__(self, o):           return self._resolve() * o
    def __rmul__(self, o):          return o * self._resolve()
    def __imul__(self, o):          return self._resolve() * o
    def __truediv__(self, o):       return self._resolve() / o
    def __rtruediv__(self, o):      return o / self._resolve()
    def __floordiv__(self, o):      return self._resolve() // o
    def __rfloordiv__(self, o):     return o // self._resolve()
    def __mod__(self, o):           return self._resolve() % o
    def __rmod__(self, o):          return o % self._resolve()
    def __pow__(self, o):           return self._resolve() ** o
    def __rpow__(self, o):          return o ** self._resolve()
    def __matmul__(self, o):        return self._resolve() @ o
    def __rmatmul__(self, o):       return o @ self._resolve()

    # ── 位运算 ────────────────────────────────────────────────────────────────

    def __and__(self, o):           return self._resolve() & o
    def __rand__(self, o):          return o & self._resolve()
    def __or__(self, o):            return self._resolve() | o
    def __ror__(self, o):           return o | self._resolve()
    def __xor__(self, o):           return self._resolve() ^ o
    def __rxor__(self, o):          return o ^ self._resolve()
    def __lshift__(self, o):        return self._resolve() << o
    def __rlshift__(self, o):       return o << self._resolve()
    def __rshift__(self, o):        return self._resolve() >> o
    def __rrshift__(self, o):       return o >> self._resolve()

    # ── 比较 ──────────────────────────────────────────────────────────────────

    def __eq__(self, o) -> bool:    return self._resolve() == o
    def __ne__(self, o) -> bool:    return self._resolve() != o
    def __lt__(self, o) -> bool:    return self._resolve() < o
    def __le__(self, o) -> bool:    return self._resolve() <= o
    def __gt__(self, o) -> bool:    return self._resolve() > o
    def __ge__(self, o) -> bool:    return self._resolve() >= o
    def __hash__(self) -> int:      return hash(self._resolve())

    # ── 容器协议 ──────────────────────────────────────────────────────────────

    def __len__(self) -> int:               return len(self._resolve())
    def __length_hint__(self) -> int:       return operator.length_hint(self._resolve())
    def __getitem__(self, k):               return self._resolve()[k]
    def __setitem__(self, k, v) -> None:    self._resolve()[k] = v
    def __delitem__(self, k) -> None:       del self._resolve()[k]
    def __contains__(self, o) -> bool:      return o in self._resolve()
    def __iter__(self) -> Iterator:         return iter(self._resolve())
    def __reversed__(self):                 return reversed(self._resolve())
    def __next__(self):                     return next(self._resolve())

    # ── 可调用 ────────────────────────────────────────────────────────────────

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)

    # ── 上下文管理器 ──────────────────────────────────────────────────────────

    def __enter__(self):
        return self._resolve().__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._resolve().__exit__(exc_type, exc_val, exc_tb)

    # ── 文件路径协议 ──────────────────────────────────────────────────────────

    def __fspath__(self) -> str:
        resolved = self._resolve()
        if hasattr(resolved, "__fspath__"):
            return resolved.__fspath__()
        return str(resolved)

    # ── 描述符协议 ────────────────────────────────────────────────────────────

    def __get__(self, obj, objtype=None):
        return self._resolve().__get__(obj, objtype)

    # ── await 支持（等待底层 Future 并返回最终结果） ───────────────────────────

    def __await__(self):
        async def _wait_for_result():
            cache = object.__getattribute__(self, "_lp_cache")
            if cache is not _MISSING:
                return cache

            fut: Future = object.__getattribute__(self, "__wrapped_future__")
            result = await asyncio.wrap_future(fut)
            object.__setattr__(self, "_lp_cache", result)
            return result

        return _wait_for_result().__await__()
