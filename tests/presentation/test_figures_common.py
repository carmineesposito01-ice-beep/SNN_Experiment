import importlib.util, pathlib
spec = importlib.util.spec_from_file_location(
    "figures_common",
    pathlib.Path(__file__).resolve().parents[2] / "presentation/_shared/figures_common.py")
fc = importlib.util.module_from_spec(spec); spec.loader.exec_module(fc)

CHAMPIONS = ["Raffaello", "Leonardo", "Donatello", "Michelangelo", "Master Splinter"]

def test_all_champions_have_a_style():
    for c in CHAMPIONS:
        s = fc.champion_style(c)
        assert set(s) >= {"color", "linestyle", "marker", "label"}

def test_styles_are_cvd_safe_distinct():
    styles = {c: fc.champion_style(c) for c in CHAMPIONS}
    keys = list(styles)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = styles[keys[i]], styles[keys[j]]
            diff = sum(a[k] != b[k] for k in ("color", "linestyle", "marker"))
            assert diff >= 2, f"{keys[i]} vs {keys[j]} too similar ({diff} channels differ)"

def test_palette_is_okabe_ito():
    assert fc.OKABE_ITO["blue"] == "#0072B2"
    assert fc.OKABE_ITO["vermillion"] == "#D55E00"

def test_unknown_champion_raises():
    import pytest
    with pytest.raises(KeyError):
        fc.champion_style("Nonexistent")
