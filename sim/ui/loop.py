"""SimLoop -- fixed-timestep driver (Fix-Your-Timestep, Glenn Fiedler), UI-agnostic.

Pure Python (no Qt): the app wires a QTimer to call tick(elapsed); tick advances
the physics in fixed dt steps and records the probe. Keeping this Qt-free makes the
loop logic fully testable without a display.
"""
from config import DT


class SimLoop:
    def __init__(self, stepper, probe=None, dt_fixed=DT):
        self.stepper = stepper
        self.probe = probe
        self.dt_fixed = float(dt_fixed)
        self._accum = 0.0

    @property
    def done(self) -> bool:
        st = self.stepper.st
        return bool(st.collided or st.t >= self.stepper.N)

    def tick(self, frame_dt):
        """Advance the sim by frame_dt seconds of real time; return the StepResults run."""
        self._accum += float(frame_dt)
        out = []
        while self._accum >= self.dt_fixed and not self.done:
            r = self.stepper.step()
            if self.probe is not None and hasattr(self.stepper.backend, "read_probe"):
                self.probe.record(r.t, self.stepper.backend.read_probe(), r.params)
            self._accum -= self.dt_fixed
            out.append(r)
        return out
