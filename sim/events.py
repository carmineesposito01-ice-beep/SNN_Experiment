"""Live events for the simulator -- deterministic per-tick queue.

v1 verb: brake_leader(target_v, duration) -- ramps the leader velocity from its
value at the trigger tick to target_v over `duration` ticks, then holds. It
overrides the scenario's leader profile from the trigger tick onward. Verb
vocabulary follows SUMO TraCI (slowDown). ReplayLog lands in Plan 3.
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
        self._events = []                       # list[Event]
        self._seq = 0
        self._brake = None                      # (t0, v_start, target, duration) | None

    def enqueue(self, tick, verb, **params):
        self._events.append(Event(tick=int(tick), seq=self._seq, verb=verb, params=params))
        self._seq += 1

    def tick(self, t, base_vl):
        """Drain events for tick t (stable order), then return the effective leader velocity."""
        for e in sorted(e for e in self._events if e.tick == t):     # order=True -> (tick, seq)
            if e.verb == "brake_leader":
                self._brake = (t, float(base_vl), float(e.params["target_v"]),
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
