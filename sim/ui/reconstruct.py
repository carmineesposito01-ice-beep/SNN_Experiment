"""reconstruct_history -- deterministic re-run of an episode into FULL-length buffers.

Deep-scrub foundation. The live probe is a 500-tick ring buffer; to scrub ticks
older than that we re-run from the ReplayLog (seed + logged events) into an
AttributeProbe/TrajectoryBuffer sized to the whole episode. Bit-identical to the
live run: same stepper.step(), same backend.read_probe(); no per-step RNG, the
scenario is a fixed array, the champion is fixed, injector.tick is deterministic.
Read-only -- the frozen core is untouched.

The oracle ghost is rebuilt here too, with backend=None. It has no SNN forward, so a
full re-run costs microseconds (against ~0.74 s for the net): it is never spliced.
"""
from sim.backend import SoftwareBackend
from sim.probe import AttributeProbe
from sim.stepper import SimStepper
from sim.ui.trajectory import TrajectoryBuffer


def _run_ghost(scenario, replaylog, n):
    """Full oracle re-run, ticks 0..n-1. Its own injector instance, rebuilt from the same log, so
    it drains the identical events."""
    ghost = SimStepper.from_scenario(None, scenario, injector=replaylog.build_injector())
    gtraj = TrajectoryBuffer(capacity=n)
    for _ in range(n):
        if ghost.st.collided or ghost.st.t >= ghost.N:
            break
        gtraj.record(ghost.step())
    return gtraj


def reconstruct_history(champion, scenario, replaylog, upto):
    """Re-run scenario 0..upto and return (probe, traj, ghost_traj) filled with every tick."""
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
    return probe, traj, _run_ghost(scenario, replaylog, n)


def reconstruct_spliced(champion, scenario, replaylog, upto, live_probe, live_traj):
    """Deep-scrub reconstruction that re-runs ONLY the pre-buffer prefix (episode_len - buffer)
    and splices it with the live ring buffer, which already holds the tail bit-identically. Cuts
    a 600-tick episode from ~7.7 s (full re-run) to ~1 s. Falls back to a full reconstruct if the
    live buffers don't cleanly cover the tail up to `upto`. The ghost is always fully re-run: with
    no SNN forward it is cheap, so the splice complexity would buy nothing."""
    live_frames = live_probe.frames()
    live_results = live_traj.results()
    ok = (live_frames and live_results and len(live_frames) == len(live_results)
          and live_frames[0].t == live_results[0].t and live_frames[-1].t == int(upto))
    prefix_len = live_frames[0].t if live_frames else 0
    if not ok or prefix_len <= 0:
        return reconstruct_history(champion, scenario, replaylog, upto)   # buffer already whole, or misaligned
    pfx_probe, pfx_traj, _ = reconstruct_history(champion, scenario, replaylog, prefix_len - 1)
    n = int(upto) + 1
    probe = AttributeProbe.from_frames(pfx_probe.frames() + live_frames, n)
    traj = TrajectoryBuffer.from_results(pfx_traj.results() + live_results, n)
    return probe, traj, _run_ghost(scenario, replaylog, n)
