"""Live events for the simulator -- deterministic per-tick queue.

v1 verb: brake_leader(target_v, duration) -- ramps the leader velocity from its
value at the trigger tick to target_v over `duration` ticks, then holds. It
overrides the scenario's leader profile from the trigger tick onward. Verb
vocabulary follows SUMO TraCI (slowDown). A full enqueue-log feeds ReplayLog.
"""
from dataclasses import dataclass, field


@dataclass(order=True)
class Event:
    tick: int
    seq: int                                    # insertion-order tiebreak (stable drain)
    verb: str = field(compare=False)
    params: dict = field(compare=False, default_factory=dict)


class EventInjector:
    def __init__(self):
        self._events = []                       # list[Event] (pending; drained per tick)
        self._seq = 0
        self._log = []                          # full enqueue history (for ReplayLog)
        self._brake = None                      # (t0, v_start, target, duration) | None

    def enqueue(self, tick, verb, **params):
        self._events.append(Event(tick=int(tick), seq=self._seq, verb=verb, params=params))
        self._log.append({"tick": int(tick), "verb": verb, "params": dict(params)})
        self._seq += 1

    def log(self):
        return [dict(e) for e in self._log]

    def tick(self, t, base_vl):
        """Drain events for tick t (stable order), then return the effective leader velocity."""
        for e in sorted(e for e in self._events if e.tick == t):     # order=True -> (tick, seq)
            if e.verb == "brake_leader":
                # Ramp from the leader's CURRENT EFFECTIVE speed, not from the raw v_leader[t]:
                # with a brake already active those differ, and using the raw value made the leader
                # teleport (measured: 5.00 -> 21.00 m/s in one tick, ~160 m/s^2). Evaluate BEFORE
                # overwriting _brake -- afterwards _effective_leader would answer about the NEW ramp.
                v_start = self._effective_leader(t, base_vl)
                self._brake = (t, v_start, float(e.params["target_v"]),
                               int(e.params["duration"]))
            else:
                raise ValueError(f"unknown verb: {e.verb!r}")
        self._events = [e for e in self._events if e.tick != t]
        return self._effective_leader(t, base_vl)

    def _effective_leader(self, t, base_vl):
        if self._brake is None:
            return float(base_vl)
        t0, v_start, target, dur = self._brake
        if t < t0:
            return float(base_vl)
        if dur <= 0 or t >= t0 + dur:
            return float(target)
        return float(v_start + (target - v_start) * ((t - t0) / dur))
