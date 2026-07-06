"""ReplayLog -- seed + event-log for bit-identical reruns (repeatable science bench).

Captures the scenario seed and the full event enqueue history so a session can be
replayed exactly (SIMULATOR_DESIGN.md §6). JSON-serializable.
"""
import json
from dataclasses import dataclass, field

from .events import EventInjector


@dataclass
class ReplayLog:
    seed: int
    events: list = field(default_factory=list)   # list of {tick, verb, params}

    @classmethod
    def from_injector(cls, seed, injector):
        return cls(seed=int(seed), events=injector.log())

    def build_injector(self):
        inj = EventInjector()
        for e in self.events:
            inj.enqueue(e["tick"], e["verb"], **e["params"])
        return inj

    def to_json(self):
        return json.dumps({"seed": self.seed, "events": self.events})

    @classmethod
    def from_json(cls, s):
        d = json.loads(s)
        return cls(seed=int(d["seed"]), events=list(d["events"]))
