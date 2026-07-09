"""Dock presets + guarded layout persistence for the simulator's DockArea shell.

visible_docks() derives the ground-truth set of placed docks from saveState() (QWidget.isVisible()
is unreliable headless). Presets arrange programmatically (moveDock/close) so they never depend on the
fragile saveState format; only the user's custom layout uses saveState/restoreState, guarded."""
import json
import os

DOCK_ORDER = ["Road", "NetState", "SpikeRate", "v_mem", "Trajectory", "Safety",
              "v0", "T", "s0", "a", "b"]
_PARAMS = ["v0", "T", "s0", "a", "b"]
LAYOUT_PATH = os.path.expanduser(os.path.join("~", ".cf_fsnn_sim", "layout.json"))


def visible_docks(area):
    """Set of dock names currently placed in the area (main + floating), from saveState()."""
    names = set()

    def walk(node):
        if not node:
            return
        kind = node[0]
        if kind == "dock":
            names.add(node[1])
        elif kind in ("horizontal", "vertical", "tab"):
            for child in node[1]:
                walk(child)

    state = area.saveState()
    walk(state.get("main"))
    for fl in state.get("float", []):
        if isinstance(fl, (list, tuple)) and fl and isinstance(fl[0], dict):
            walk(fl[0].get("main"))
    return names


def _show(area, docks, name, position, neighbor=None):
    ref = docks[neighbor] if neighbor else None
    area.addDock(docks[name], position, ref)   # re-adds if closed; moves if already placed


def _hide(docks, name):
    docks[name].close()   # idempotent; safe even if already closed


def apply_overview(area, docks):
    _show(area, docks, "Road", "top")
    _show(area, docks, "NetState", "bottom", "Road")
    _show(area, docks, "v_mem", "bottom", "NetState")
    _show(area, docks, "Trajectory", "right", "v_mem")
    _show(area, docks, "Safety", "right", "Trajectory")
    _show(area, docks, "v0", "bottom", "v_mem")
    for prev, n in zip(["v0", "T", "s0", "a"], ["T", "s0", "a", "b"]):
        _show(area, docks, n, "right", prev)
    _show(area, docks, "SpikeRate", "right", "NetState")   # last: split NetState's row -> NetState | SpikeRate


def apply_guida(area, docks):
    for d in ("NetState", "SpikeRate", "v_mem"):
        _hide(docks, d)
    _show(area, docks, "Road", "top")
    _show(area, docks, "Trajectory", "bottom", "Road")   # driving story: road + trajectory + safety
    _show(area, docks, "Safety", "right", "Trajectory")
    _show(area, docks, "v0", "bottom", "Trajectory")
    for n in ["T", "s0", "a", "b"]:
        _show(area, docks, n, "above", "v0")   # tab-stack params together


def apply_identificazione(area, docks):
    for d in ("v_mem", "NetState", "SpikeRate", "Trajectory", "Safety"):
        _hide(docks, d)
    _show(area, docks, "Road", "top")
    _show(area, docks, "v0", "bottom", "Road")
    for prev, n in zip(["v0", "T", "s0", "a"], ["T", "s0", "a", "b"]):
        _show(area, docks, n, "bottom", prev)   # 5 params stacked, dominant


def apply_neuro_debug(area, docks):
    _hide(docks, "Trajectory")
    _hide(docks, "Safety")
    _show(area, docks, "NetState", "left")
    _show(area, docks, "SpikeRate", "right", "NetState")
    _show(area, docks, "v_mem", "bottom", "NetState")
    _show(area, docks, "Road", "bottom", "v_mem")
    _show(area, docks, "v0", "right", "SpikeRate")
    for n in ["T", "s0", "a", "b"]:
        _show(area, docks, n, "above", "v0")   # params tab-stacked, compact


PRESETS = {"Overview": apply_overview, "Guida": apply_guida,
           "Identificazione": apply_identificazione, "Neuro-debug": apply_neuro_debug}


def save_layout(area, path=LAYOUT_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(area.saveState(), f)


def load_layout(area, docks, path=LAYOUT_PATH):
    """Restore a saved layout, guarded. Returns True on success, False if it fell back to Overview
    (missing file OR any restore error — the pyqtgraph 0.14 restoreState bug safety net)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        area.restoreState(state)
        return True
    except Exception:
        apply_overview(area, docks)
        return False
