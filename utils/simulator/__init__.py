"""
utils/simulator — Simulatore visivo CF_FSNN per validazione operativa pre-FPGA.

Public API:
    - CFSimulator: engine principale (load + simulate)
    - compute_operational_metrics: 9 metriche per-scenario
    - aggregate_metrics: aggregazione per scenario_type
    - plot_simulation_static, plot_topdown_snapshot: figure builders statici
    - animate_scenario: matplotlib FuncAnimation + GIF/MP4 export
"""
from utils.simulator.engine import CFSimulator
from utils.simulator.metrics import compute_operational_metrics, aggregate_metrics
from utils.simulator.plots import plot_simulation_static, plot_topdown_snapshot
from utils.simulator.anim import animate_scenario, save_animation

__all__ = [
    'CFSimulator',
    'compute_operational_metrics', 'aggregate_metrics',
    'plot_simulation_static', 'plot_topdown_snapshot',
    'animate_scenario', 'save_animation',
]
