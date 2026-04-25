import sys, time, operator, math, tempfile, os
sys.path.insert(0, ".")

import pytest
from concurrent.futures import ThreadPoolExecutor
from autoasync import LazyProxy

_pool = ThreadPoolExecutor()

def make(val, delay=0.0):
    def _f():
        if delay: time.sleep(delay)
        return val
    return LazyProxy(_pool.submit(_f))

# ── 字符串/表示 ───────────────────────────────────────────
def test_str():    assert str(make("hi")) == "hi"
def test_bytes():  assert bytes(make(b"ab")) == b"ab"
def test_format(): assert f"{make(3.14):.1f}" == "3.1"

def test_repr_pending():
    p = make(42, delay=1.0)
    assert repr(p) == "<LazyProxy [pending]>"

def test_repr_done():
    p = make(42, delay=0.0)
    time.sleep(0.05)
    assert repr(p) == "42"

# ── 数値変換 ──────────────────────────────────────────────
def test_int():     assert int(make(3.9)) == 3
def test_float():   assert float(make(2)) == 2.0
def test_bool_t():  assert bool(make(1))
def test_bool_f():  assert not bool(make(0))
def test_complex(): assert complex(make(1)) == complex(1)
def test_index():   assert operator.index(make(5)) == 5
def test_round():   assert round(make(3.567), 2) == 3.57
def test_trunc():   assert math.trunc(make(3.9)) == 3
def test_floor():   assert math.floor(make(3.9)) == 3
def test_ceil():    assert math.ceil(make(3.1)) == 4

# ── 一元 ─────────────────────────────────────────────────
def test_abs():     assert abs(make(-5)) == 5
def test_neg():     assert -make(3) == -3
def test_pos():     assert +make(3) == 3
def test_invert():  assert ~make(0) == -1

# ── 算術 ─────────────────────────────────────────────────
def test_add():        assert make(10) + 5 == 15
def test_radd():       assert 5 + make(10) == 15
def test_sub():        assert make(10) - 3 == 7
def test_rsub():       assert 20 - make(10) == 10
def test_mul():        assert make(4) * 3 == 12
def test_rmul():       assert 3 * make(4) == 12
def test_truediv():    assert make(10) / 4 == 2.5
def test_rtruediv():   assert 20 / make(4) == 5.0
def test_floordiv():   assert make(10) // 3 == 3
def test_mod():        assert make(10) % 3 == 1
def test_pow():        assert make(2) ** 8 == 256
def test_rpow():       assert 2 ** make(8) == 256

# ── 位演算 ────────────────────────────────────────────────
def test_and():      assert make(0b1010) & 0b1100 == 0b1000
def test_rand():     assert 0b1100 & make(0b1010) == 0b1000
def test_or():       assert make(0b1010) | 0b0101 == 0b1111
def test_xor():      assert make(0b1111) ^ 0b1010 == 0b0101
def test_lshift():   assert make(1) << 4 == 16
def test_rshift():   assert make(16) >> 2 == 4

# ── 比較 ─────────────────────────────────────────────────
def test_eq():   assert make(1) == 1
def test_ne():   assert make(1) != 2
def test_lt():   assert make(1) < 2
def test_le():   assert make(1) <= 1
def test_gt():   assert make(2) > 1
def test_ge():   assert make(2) >= 2
def test_hash(): assert hash(make(42)) == hash(42)

# ── コンテナ ─────────────────────────────────────────────
def test_len():       assert len(make([1,2,3])) == 3
def test_getitem():   assert make([10,20,30])[1] == 20
def test_contains():  assert 2 in make([1,2,3])
def test_iter():      assert list(make([1,2,3])) == [1,2,3]
def test_reversed():  assert list(reversed(make([1,2,3]))) == [3,2,1]

def test_setitem():
    p = make([1,2,3])
    p[0] = 99
    assert p[0] == 99

def test_delitem():
    p = make([1,2,3])
    del p[2]
    assert len(p) == 2

# ── 呼び出し可能 ─────────────────────────────────────────
def test_call():
    assert make(lambda x: x * 3)(4) == 12

# ── コンテキストマネージャ ──────────────────────────────
def test_context_manager():
    class CM:
        def __enter__(self): return "inside"
        def __exit__(self, *a): pass
    with make(CM()) as val:
        assert val == "inside"

# ── ファイルパスプロトコル ──────────────────────────────
def test_fspath(tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("ok")
    with open(make(str(f))) as fh:
        assert fh.read() == "ok"

# ── 属性アクセス ─────────────────────────────────────────
def test_getattr():
    assert make("hello").upper() == "HELLO"

# ── 並行性 ───────────────────────────────────────────────
def test_concurrent():
    t0 = time.perf_counter()
    a = make(1, delay=0.3)
    b = make(2, delay=0.3)
    c = make(3, delay=0.3)
    assert a + b + c == 6
    assert time.perf_counter() - t0 < 0.6
