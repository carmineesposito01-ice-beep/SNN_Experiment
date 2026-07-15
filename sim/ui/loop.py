"""SimLoop -- fixed-timestep driver (Fix-Your-Timestep, Glenn Fiedler), UI-agnostic.

Pure Python (no Qt): the app wires a QTimer to call tick(elapsed); tick advances
the physics in fixed dt steps and records the probe. Keeping this Qt-free makes the
loop logic fully testable without a display.

Optionally drives a second stepper -- the ORACLE ghost (SimStepper with backend=None,
constant true params). It must advance here and nowhere else: the loop owns the
accumulator, so it is the only place that can guarantee the two stay in lockstep, and
lockstep is what makes them share the same leader tick (the injector is shared and its
tick() is idempotent -- measured, see the spec).
"""
from config import DT


class SimLoop:
    def __init__(self, stepper, probe=None, dt_fixed=DT, ghost=None, ghost_traj=None):
        self.stepper = stepper
        self.probe = probe
        self.dt_fixed = float(dt_fixed)
        self.ghost = ghost                  # SimStepper(backend=None) | None
        self.ghost_traj = ghost_traj        # TrajectoryBuffer | None
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
            self._step_ghost()
            self._accum -= self.dt_fixed
            out.append(r)
        return out

    def _step_ghost(self):
        """Advance the oracle exactly once per net step. If the oracle finished (collided or ran
        out of profile) it holds its last state: the episode is the NET's episode -- `done` reads
        the net's stepper, not this one."""
        if self.ghost is None:
            return
        gst = self.ghost.st
        if gst.collided or gst.t >= self.ghost.N:
            return
        rg = self.ghost.step()
        if self.ghost_traj is not None:
            self.ghost_traj.record(rg)
