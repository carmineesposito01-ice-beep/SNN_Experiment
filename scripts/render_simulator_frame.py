"""Offscreen: advance the sim a few seconds and grab the window to a PNG (visual check)."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication   # noqa: E402
from sim.ui.app import SimApp                # noqa: E402
from sim.ui.theme import apply_dark_theme    # noqa: E402

DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "champions", "R33_C2_A1_T12_fix", "best_model.pt")


def main():
    app = QApplication([])
    apply_dark_theme(app)
    win = SimApp(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
    win.resize(1000, 760)
    win.show()
    win.select_scenario([s.name for s in win._scenarios].index("following"))
    for _ in range(20):
        win._advance(0.1)
    win.inject_brake()                       # brake the leader -> gap shrinks, TTC colour changes
    for _ in range(60):
        win._advance(0.1)
    app.processEvents()
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sim_frame.png")
    win.grab().save(out)
    print("wrote", out, "|", win.loop.stepper.st.t, "steps | collided", win.loop.stepper.st.collided)


if __name__ == "__main__":
    main()
