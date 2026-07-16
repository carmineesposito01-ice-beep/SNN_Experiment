import os
import struct
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.mat_writer import write_mat   # noqa: E402


def _read_mat(path):
    """A minimal paired MAT v5 reader -- test-only, to round-trip the writer."""
    with open(path, "rb") as f:
        raw = f.read()
    assert raw[124:128] == struct.pack("<HH", 0x0100, 0x4D49)   # version + little-endian ('MI' read LE)
    out, off = {}, 128
    while off < len(raw):
        dtype, nbytes = struct.unpack("<II", raw[off:off + 8]); off += 8
        body = raw[off:off + nbytes]; off += nbytes + ((-nbytes) % 8)
        assert dtype == 14                                       # miMATRIX
        p = 0

        def take():
            nonlocal p
            t, n = struct.unpack("<II", body[p:p + 8]); p += 8
            d = body[p:p + n]; p += n + ((-n) % 8)
            return t, d

        _, flags = take(); cls = struct.unpack("<II", flags)[0] & 0xFF
        _, dims_b = take(); d0, d1 = struct.unpack("<ii", dims_b)
        _, name_b = take(); name = name_b.decode("ascii")
        _, real = take()
        out[name] = real.decode("utf-16-le") if cls == 4 else np.frombuffer(real, "<f8").reshape(d0, d1)
    return out


def test_write_mat_roundtrips_array_scalar_and_string(tmp_path):
    p = str(tmp_path / "x.mat")
    write_mat(p, {"v_leader": np.array([1.0, 2.0, 3.0]), "s_init": 12.5, "name": "myrun"})
    got = _read_mat(p)
    assert np.allclose(got["v_leader"].ravel(), [1.0, 2.0, 3.0])
    assert np.allclose(got["s_init"].ravel(), [12.5])
    assert got["name"] == "myrun"


def test_write_mat_matches_the_v5_spec_bytes(tmp_path):
    p = str(tmp_path / "y.mat")
    write_mat(p, {"v": np.array([1.0, 2.0])})
    raw = (tmp_path / "y.mat").read_bytes()
    assert len(raw) >= 128
    assert raw[124:128] == struct.pack("<HH", 0x0100, 0x4D49)    # version 0x0100 + endian 'IM'
    assert struct.unpack("<I", raw[128:132])[0] == 14           # first element tag = miMATRIX
    # first sub-element (array flags) carries the class byte: mxDOUBLE_CLASS = 6
    flags_val = struct.unpack("<I", raw[128 + 8 + 8:128 + 8 + 8 + 4])[0]
    assert (flags_val & 0xFF) == 6
