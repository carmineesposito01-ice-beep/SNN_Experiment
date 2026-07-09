"""reconstruct_history -- deterministic re-run of an episode into FULL-length buffers.

Deep-scrub foundation. The live probe is a 500-tick ring buffer; to scrub ticks
older than that we re-run from the ReplayLog (seed + logged events) into an
AttributeProbe/TrajectoryBuffer sized to the whole episode. Bit-identical to the
live run: same stepper.step(), same backend.read_probe(); no per-step RNG, the
scenario is a fixed array, the champion is fixed, injector.tick is deterministic.
Read-only -- the frozen core is untouched.
"""
from sim.backend import SoftwareBackend
from sim.probe import AttributeProbe
from sim.stepper import SimStepper
from sim.ui.trajectory import TrajectoryBuffer


def reconstruct_history(champion, scenario, replaylog, upto):
    """Re-run scenario 0..upto and return (probe, traj) filled with every tick."""
    n = int(upto) + 1
    backend = SoftwareBackend(champion.model)
    stepper = SimStepper.from_scenario(backend, scenario,
                                       injector=replaylog.build_injector())
    probe = AttributeProbe(capacity=n)
    traj = TrajectoryBuffer(capacity=n)
    for _ in range(n):
        if stepper.st.collided or stepper.st.t >= stepper.N:
            break
        r = stepper.step()
        probe.record(r.t, backend.read_probe(), r.params)
        traj.record(r)
    return probe, traj
