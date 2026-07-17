"""The export-format registry: the SINGLE source of truth for which formats exist, who writes them, how big
they are, and -- when unavailable -- why.

The UI renders its checkboxes FROM this registry, so no hardcoded list elsewhere can diverge from reality.

parquet and hdf5 are registered but unavailable: pyarrow/h5py are COMPILED libraries and this env has a known
OpenMP fragility (the OMP #15 abort is duplicate OMP runtimes; torch already brings one). Risking a green suite
for a format no consumer has asked for is a bad trade -- so they are declared, disabled, and explained.
Enabling one later = install the dep + a small writer + flip `available`.

bytes_per_tick is calibrated against REAL measurements (CSV 60438 B and MAT 20072 B for N=600) and pinned by a
test that re-measures it -- the estimate cannot drift in silence."""
import json
import zipfile
from dataclasses import dataclass
from typing import Callable, Optional

from config import DT
from sim.scenario_export import (leader_kinematics, scenario_metadata, write_scenario_csv,
                                 write_scenario_mat)


@dataclass(frozen=True)
class FormatSpec:
    writer: Callable          # (scenario, path, dt) -> None
    bytes_per_tick: float     # calibrated; pinned by test_bytes_per_tick_matches_a_measured_sample
    available: bool
    reason: Optional[str] = None


def _write_json(scenario, path, dt=DT):
    k = leader_kinematics(scenario, dt)
    m = scenario_metadata(scenario, dt)
    payload = {**{key: [float(x) for x in arr] for key, arr in k.items()},
               "name": m["name"], "dt": m["dt"], "N": m["N"],
               "s_init": m["s_init"], "v_init": m["v_init"],
               "params_gt": [float(x) for x in m["params_gt"]]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


_CT = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
       '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
       '<Default Extension="xml" ContentType="application/xml"/>'
       '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.'
       'spreadsheetml.sheet.main+xml"/>'
       '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-'
       'officedocument.spreadsheetml.worksheet+xml"/></Types>')
_RELS = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
         'relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
         'relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
_WB = ('<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
       '<sheet name="scenario" sheetId="1" r:id="rId1"/></sheets></workbook>')
_WB_RELS = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')


def _col(i):
    """0 -> A, 1 -> B, ... (only 4 columns here, but keep it general)."""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _write_xlsx(scenario, path, dt=DT):
    """A minimal .xlsx: a zip of XML parts (stdlib only -- openpyxl/xlsxwriter are absent).

    Same school as the hand-rolled MAT v5 writer, and easier: this is text, not binary tags. A header row +
    one row per tick, inline numbers (no sharedStrings needed for a numeric sheet)."""
    k = leader_kinematics(scenario, dt)
    cols = ["t", "v_leader", "x_leader", "a_leader"]
    rows = ['<row r="1">' + "".join(
        f'<c r="{_col(j)}1" t="inlineStr"><is><t>{c}</t></is></c>' for j, c in enumerate(cols)) + "</row>"]
    n = len(k["t"])
    for i in range(n):
        cells = "".join(f'<c r="{_col(j)}{i + 2}"><v>{float(k[c][i]):.6g}</v></c>' for j, c in enumerate(cols))
        rows.append(f'<row r="{i + 2}">{cells}</row>')
    sheet = ('<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/'
             'main"><sheetData>' + "".join(rows) + "</sheetData></worksheet>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CT)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("xl/workbook.xml", _WB)
        z.writestr("xl/_rels/workbook.xml.rels", _WB_RELS)
        z.writestr("xl/worksheets/sheet1.xml", sheet)


def _unavailable(dep):
    def _refuse(scenario, path, dt=DT):
        raise RuntimeError(f"formato non disponibile: richiede {dep}")
    return _refuse


FORMATS = {
    "csv":     FormatSpec(write_scenario_csv, 100.7, True),    # measured: 60438 B / 600 ticks
    "mat":     FormatSpec(write_scenario_mat, 33.5, True),     # measured: 20072 B / 600 ticks
    "json":    FormatSpec(_write_json, 70.0, True),            # measured: 42019 B / 600 ticks
    "xlsx":    FormatSpec(_write_xlsx, 31.6, True),            # measured: 18954 B / 600 ticks (zipped XML)
    "parquet": FormatSpec(_unavailable("pyarrow"), 12.0, False, "richiede pyarrow"),
    "hdf5":    FormatSpec(_unavailable("h5py"), 33.0, False, "richiede h5py"),
}


def available_formats():
    return [k for k, v in FORMATS.items() if v.available]


def estimate_bytes(ticks_per_traj, formats):
    """Sum over trajectories x selected formats. An estimate: float formatting varies."""
    total_ticks = float(sum(ticks_per_traj))
    return sum(total_ticks * FORMATS[f].bytes_per_tick for f in formats)
