"""The dataset mix: which scenarios, from which family, at what percentage -- and the EXACT counts that follow.

Exact quotas, not a multinomial draw: "30%" for a controlled dataset means exactly 30 trajectories out of 100,
not 30 in expectation. The leftovers from rounding go to the largest remainders, so the counts always sum to N
and no trajectory is lost."""
from dataclasses import dataclass

FAMILIES = ("built", "preset", "generator")


@dataclass(frozen=True)
class MixEntry:
    family: str      # one of FAMILIES
    source: str      # a built scenario's name | a library preset name | a generator profile name
    weight: float    # percent; the mix must total 100


def validate_mix(mix, families=FAMILIES):
    """Raise ValueError unless the mix is non-empty, every family is known, and the weights total 100.

    `families` (default: 7a's three) is additive so 7b can reuse this arithmetic with its own vocabulary --
    cut_in is a training family only. Every existing caller passes nothing and gets today's behaviour."""
    if not mix:
        raise ValueError("mix vuoto")
    for e in mix:
        if e.family not in families:
            raise ValueError(f"famiglia sconosciuta: {e.family!r} (valide: {families})")
        if e.weight < 0:
            raise ValueError(f"peso negativo: {e.weight}")
    total = sum(e.weight for e in mix)
    if abs(total - 100.0) > 0.01:
        raise ValueError(f"i pesi non sommano a 100 (somma={total:.2f})")


def quotas(mix, count, families=FAMILIES):
    """Exact per-entry counts summing to `count` (largest remainder for the leftovers)."""
    validate_mix(mix, families)
    raw = [e.weight / 100.0 * count for e in mix]
    base = [int(x) for x in raw]
    left = count - sum(base)
    order = sorted(range(len(mix)), key=lambda i: raw[i] - base[i], reverse=True)
    for i in order[:left]:
        base[i] += 1
    return base
