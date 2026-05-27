# CF_FSNN — Car-Following Spiking Neural Network

Physics-informed SNN for real-time identification of car-following parameters
from V2X (V2V/V2I) signals, targeting deployment on PYNQ-Z1 FPGA.

## Architecture

```
Input (4)  →  HiddenLayer_ALIF (32, rank=8, delay=6)  →  OutputLayer_LI (5)
[s, v, Δv, v_l]   ALIF neurons + low-rank recurrence       [v₀, T, s₀, a, b]
```

- **864 total parameters** — fits in PYNQ-Z1 BRAM with Po2 quantization
- **ACC-IDM (IIDM base)**: physical model used in both data generation and PINN loss
- **PINN loss**: SRMSE + physics residual + OU mean-reversion + crash penalty

## Physical Model: ACC-IDM with IIDM base

The Intelligent Driver Model extended with:

1. **IIDM base** — separates free-flow (z<1) and car-following (z≥1) regimes, eliminating IDM's near-v₀ speed bias
2. **CAH** (Constant Acceleration Heuristic) — anticipatory braking response to leader behaviour
3. **ACC blend** — `a = (1-c)·a_IIDM + c·(a_CAH + b·tanh((a_IIDM - a_CAH)/b))` with c=0.99

Leader acceleration `a_l` is estimated from OU-filtered finite differences on `v_l` (τ=1s), replicating the real V2X chain without ground-truth leakage.

## Dataset (synthetic, ACC-IDM)

| Split | Trajectories | Duration | Scenarios |
|-------|-------------|----------|-----------|
| Train | 500 | 200s each | highway, urban, truck, mixed |
| Val   | 100 | 200s each | same mix |
| Test  | 200 | 200s each | held-out seed |

- **IDM-2d** (Ch12.6): stochastic T(t) extension via Ornstein-Uhlenbeck (τ=30s, band [0.8, 1.6]s) — applied to ACC-IDM
- **Cut-in UC2**: 20% of trajectories include an abrupt cut-in event (gap → 5–15m)
- **V2X packet loss**: 2% (ETSI ITS-G5 simulation)
- **OU perception noise** on s, v, a (Ch13 Treiber & Kesting)

## Training

```bash
# Quick test (1 epoch, CPU)
python train.py --epochs 1 --tag QUICKTEST --n_train 50 --n_val 20

# Stage A: baseline (20 epochs, plateau scheduler)
python train.py --epochs 20 --scheduler plateau --tag A1_plateau

# Stage B: OneCycleLR + Lion optimizer
python train.py --epochs 50 --scheduler onecycle --optimizer lion \
    --max_lr 5e-3 --tag B1_lion_onecycle

# Stage C: resume from best checkpoint
python train.py --epochs 100 --scheduler cosine --T0 10 \
    --resume checkpoints/B1_lion_onecycle/best_model.pt --tag C1_cosine
```

### On Azure (GPU)
The device is auto-detected via `config.py → DEVICE`. No code change needed:
```bash
python train.py --epochs 100 --scheduler onecycle --optimizer lion \
    --batch_size 32 --max_lr 5e-3 --tag AZURE_v1
```

## Output (per run)

```
checkpoints/<tag>/
  best_model.pt          # best val_loss checkpoint
  last_model.pt          # last epoch checkpoint
  training_log.csv       # 15 columns per epoch (loss components, LR, grad, spike)
  config_snapshot.json   # full hyperparameter record
  plots/
    G1_loss_curve.png    # train/val total loss
    G2_components.png    # loss components (data, phys, OU, bc)
    G3_lr_schedule.png   # learning rate schedule
    G4_grad_norm.png     # gradient norm (exploding/vanishing check)
    G5_T_scatter.png     # T_pred vs T_true scatter (val set, best model)
    G6_spike_rate.png    # hidden layer spike rate (target: 10–20%)
    G7_violin_params.png # predicted parameter distributions vs physical bounds
```

## Evaluation (post-training)

```bash
python eval_report.py --checkpoint checkpoints/<tag>/best_model.pt --n_test 500
```

Produces:
- PINN loss metrics on held-out test set (mean/std/min/max per component)
- Per-parameter statistics with physical bounds compliance (%)
- MAE, RMSE, Bias on T (time-gap estimation)
- G5 and G7 plots saved in `checkpoints/<tag>/eval_plots/`

## Hardware Target

- **PYNQ-Z1** (Xilinx Zynq-7020, 220 DSP48E1, 4.9MB BRAM)
- **Po2 quantization**: weights ∈ {2⁻⁴, …, 2¹} → bit-shift multiply, zero DSP usage
- **Inference**: 100ms per V2X frame (10Hz ETSI ITS-G5), fits in BRAM with ~3× margin

## Project Structure

```
CF_FSNN/
  config.py              # all hyperparameters
  train.py               # training loop (PINN, TBPTT, schedulers, logging)
  eval_report.py         # post-training evaluation on test set
  core/
    network.py           # CF_FSNN_Net (ALIF→LI), acc_iidm_accel()
    neurons.py           # ALIFCell, LICell (surrogate gradient γ=0.3)
    hardware.py          # po2_quantize()
  data/
    generator.py         # ACC-IDM synthetic data, cut-in UC2
  utils/
    plot_diagnostics.py  # G1–G7 diagnostic plots
  document/
    project_core_guidelines.md  # authoritative project reference
    training_plan.md            # stage A/B/C training plan
    correction.md               # model corrections vs IDM plain
    optimization_ideas.md       # future optimisation roadmap
```

## References

- Treiber & Kesting, *Traffic Flow Dynamics* 2nd ed. (Springer 2025)
  - Ch12: IDM, IIDM, ACC-IDM, IDM-2D, stochastic extensions
  - Ch13: Human driver model, OU noise, perception errors
  - Ch17: PINN calibration, SRMSE as goodness-of-fit
- Chen et al. (2023): Lion optimizer
- ETSI EN 302 637-2: ITS-G5 V2X standard (10Hz, 2% packet loss)
