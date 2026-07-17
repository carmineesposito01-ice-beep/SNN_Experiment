import json
import os
import sys
import zipfile

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from config import DT                                    # noqa: E402
from sim.scenario import scenario_library                # noqa: E402
from sim.export_formats import FORMATS, available_formats, estimate_bytes   # noqa: E402

_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


def test_the_registry_knows_all_six_and_flags_the_unavailable_ones():
    assert set(FORMATS) == {"csv", "mat", "json", "xlsx", "parquet", "hdf5"}
    assert set(available_formats()) == {"csv", "mat", "json", "xlsx"}
    assert FORMATS["parquet"].available is False and "pyarrow" in FORMATS["parquet"].reason
    assert FORMATS["hdf5"].available is False and "h5py" in FORMATS["hdf5"].reason


def test_every_available_writer_produces_a_readable_file(tmp_path):
    sc = scenario_library(_PG, N=60)[0]
    for name in available_formats():
        p = str(tmp_path / f"s.{name}")
        FORMATS[name].writer(sc, p, DT)
        assert os.path.getsize(p) > 0
    # json round-trips its four columns
    with open(str(tmp_path / "s.json")) as f:
        d = json.load(f)
    assert len(d["v_leader"]) == 60 and set(["t", "v_leader", "x_leader", "a_leader"]) <= set(d)
    # xlsx is a real zip with a sheet in it
    with zipfile.ZipFile(str(tmp_path / "s.xlsx")) as z:
        assert "xl/worksheets/sheet1.xml" in z.namelist()


def test_bytes_per_tick_matches_a_measured_sample(tmp_path):
    """The estimate must not silently drift from what the writers actually produce."""
    sc = scenario_library(_PG, N=600)[0]
    for name in available_formats():
        p = str(tmp_path / f"m.{name}")
        FORMATS[name].writer(sc, p, DT)
        measured = os.path.getsize(p) / 600.0
        claimed = FORMATS[name].bytes_per_tick
        assert abs(measured - claimed) / measured < 0.10, f"{name}: claimed {claimed}, measured {measured:.1f}"


def test_estimate_sums_over_ticks_and_formats():
    one = estimate_bytes([600], ["csv"])
    assert abs(one - 600 * FORMATS["csv"].bytes_per_tick) < 1.0
    both = estimate_bytes([600, 300], ["csv", "mat"])
    assert abs(both - (900 * FORMATS["csv"].bytes_per_tick + 900 * FORMATS["mat"].bytes_per_tick)) < 1.0


def test_an_unavailable_format_refuses_to_write(tmp_path):
    sc = scenario_library(_PG, N=10)[0]
    with pytest.raises(RuntimeError):
        FORMATS["parquet"].writer(sc, str(tmp_path / "x.parquet"), DT)
