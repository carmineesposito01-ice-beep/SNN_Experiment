"""A minimal, dependency-free MAT-file Level-5 writer (scipy is absent in this env, and its LAPACK pull-in is
the OMP #15 abort we avoid). Serialises a flat {name: value} dict as top-level variables, so MATLAB
`load('f.mat')` binds each name in the workspace. Supports float64 arrays, real scalars, and strings -- the
only types a leader-kinematics export needs. Everything is little-endian; every element is 8-byte aligned."""
import struct

import numpy as np

_MI_INT8, _MI_INT32, _MI_UINT16, _MI_UINT32, _MI_DOUBLE, _MI_MATRIX = 1, 5, 4, 6, 9, 14
_MX_CHAR, _MX_DOUBLE = 4, 6


def _element(dtype, data):
    """An 8-byte tag [type, nbytes] + data padded up to an 8-byte boundary."""
    return struct.pack("<II", dtype, len(data)) + data + b"\x00" * ((-len(data)) % 8)


def _matrix(name, value):
    if isinstance(value, str):
        cls, dims, real = _MX_CHAR, (1, len(value)), _element(_MI_UINT16, value.encode("utf-16-le"))
    else:
        arr = np.asarray(value, dtype="<f8")
        cls = _MX_DOUBLE
        dims = (1, 1) if arr.ndim == 0 else (1, arr.size)
        real = _element(_MI_DOUBLE, arr.tobytes())
    flags = _element(_MI_UINT32, struct.pack("<II", cls, 0))         # array flags (class in the low byte)
    dim_e = _element(_MI_INT32, struct.pack("<ii", dims[0], dims[1]))
    name_e = _element(_MI_INT8, name.encode("ascii"))
    return _element(_MI_MATRIX, flags + dim_e + name_e + real)


def write_mat(path, variables):
    """Write {name: np.ndarray | float | int | str} to a Level-5 .mat file at `path`."""
    text = b"MATLAB 5.0 MAT-file, cf_sim scenario export"
    header = text.ljust(116, b" ") + b"\x00" * 8 + struct.pack("<HH", 0x0100, 0x4D49)
    with open(path, "wb") as f:
        f.write(header)
        for name, value in variables.items():
            f.write(_matrix(name, value))
