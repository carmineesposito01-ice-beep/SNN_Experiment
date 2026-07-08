"""Launch the CF_FSNN simulator. Usage: python scripts/run_simulator.py [champion.pt]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication   # noqa: E402
from sim.ui.app import SimApp                # noqa: E402
from sim.ui.layout import LAYOUT_PATH        # noqa: E402
from sim.ui.theme import apply_dark_theme    # noqa: E402

DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "champions", "R33_C2_A1_T12_fix", "best_model.pt")


def main():
    champ = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    app = QApplication(sys.argv)
    apply_dark_theme(app)
    win = SimApp(champ, layout_path=LAYOUT_PATH)
    win.resize(1000, 760)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
