"""
eval_report.py -- Valutazione quantitativa del modello CF_FSNN addestrato.
Genera metriche dettagliate su dati di test mai visti durante il training.
"""
import sys, os, torch, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (SEED, set_seed, NORM_S_MAX, NORM_V_MAX, NORM_DV_MAX,
                    LAMBDA_DATA, LAMBDA_PHYS, LAMBDA_OU, LAMBDA_BC,
                    IDM2D_T1, IDM2D_T2)
from core.network import CF_FSNN_Net
from data.generator import generate_dataset
from train import CFDataset, pinn_loss
from torch.utils.data import DataLoader

set_seed(SEED + 99)   # seed diverso da train/val

# ─── carica modello ────────────────────────────────────────────────────────
model = CF_FSNN_Net()
ck    = torch.load('checkpoints/best.pt', map_location='cpu')
model.load_state_dict(ck['model_state'])
model.eval()
print(f"Modello caricato da epoch {ck['epoch']}  |  val_loss_salvata={ck['val_loss']:.6f}\n")

# ─── genera test set ───────────────────────────────────────────────────────
N_TEST = 200
print(f"Generazione {N_TEST} traiettorie di test (seed={SEED+99})...")
test_data = generate_dataset(N_TEST, base_seed=SEED + 99)
test_ds   = CFDataset(test_data, seq_len=100, stride=100)   # finestre non-overlap
test_dl   = DataLoader(test_ds, batch_size=32, shuffle=False, num_workers=0)
print(f"Finestre test: {len(test_ds)}  |  Batch: {len(test_dl)}\n")

# ─── valutazione ────────────────────────────────────────────────────────────
all_losses   = {'total':[], 'data':[], 'phys':[], 'ou':[], 'bc':[]}
pred_params  = []
gt_T         = []

with torch.no_grad():
    for x, y, mask in test_dl:
        loss, comps = pinn_loss(model, x, y, mask)
        all_losses['total'].append(loss.item())
        for k in ['data','phys','ou','bc']:
            all_losses[k].append(comps[k])

        params_seq = model.forward_sequence(x)   # (batch, T, 5)
        pred_params.append(params_seq.numpy())
        gt_T.append(y[:, :, 1].numpy())

# ─── statistiche loss ────────────────────────────────────────────────────────
print("=" * 60)
print("  METRICHE DI LOSS (test set -- mai visto in training)")
print("=" * 60)
for k in ['total','data','phys','ou','bc']:
    arr = np.array(all_losses[k])
    print(f"  {k:10s}  mean={arr.mean():.5f}  std={arr.std():.5f}  "
          f"min={arr.min():.5f}  max={arr.max():.5f}")

# ─── analisi parametri predetti ──────────────────────────────────────────────
pred_np = np.concatenate(pred_params, axis=0)
gt_T_np = np.concatenate(gt_T,        axis=0)

names_out = ['v0 [m/s]', 'T [s]', 's0 [m]', 'a [m/s2]', 'b [m/s2]']
bounds_lo = [8.0, 0.5, 1.0, 0.3, 0.5]
bounds_hi = [45., 2.5, 5.0, 2.5, 3.0]

print()
print("=" * 60)
print("  PARAMETRI IDM-2D PREDETTI (media su tutte le finestre)")
print("=" * 60)
for i, name in enumerate(names_out):
    p = pred_np[:, :, i].flatten()
    print(f"  {name:12s}  mean={p.mean():.3f}  std={p.std():.3f}  "
          f"min={p.min():.3f}  max={p.max():.3f}  "
          f"[atteso: {bounds_lo[i]:.1f}..{bounds_hi[i]:.1f}]")

# ─── T predetto vs T_true ───────────────────────────────────────────────────
T_pred = pred_np[:, :, 1].flatten()
T_true = gt_T_np.flatten()
mae_T  = np.mean(np.abs(T_pred - T_true))
rmse_T = math.sqrt(np.mean((T_pred - T_true) ** 2))

print()
print("=" * 60)
print("  STIMA T (time-gap): predetto vs ground truth")
print("=" * 60)
print(f"  T_true  mean={T_true.mean():.3f}  std={T_true.std():.3f}  "
      f"range=[{T_true.min():.3f}, {T_true.max():.3f}]")
print(f"  T_pred  mean={T_pred.mean():.3f}  std={T_pred.std():.3f}  "
      f"range=[{T_pred.min():.3f}, {T_pred.max():.3f}]")
print(f"  MAE(T)  = {mae_T:.4f} s")
print(f"  RMSE(T) = {rmse_T:.4f} s")
print(f"  IDM2D banda attesa T in [{IDM2D_T1}, {IDM2D_T2}] s")

# ─── rispetto bounds fisici ─────────────────────────────────────────────────
print()
print("=" * 60)
print("  RISPETTO DEI BOUNDS FISICI (% campioni entro range)")
print("=" * 60)
for i, name in enumerate(names_out):
    p = pred_np[:, :, i].flatten()
    pct = np.mean((p >= bounds_lo[i]) & (p <= bounds_hi[i])) * 100
    print(f"  {name:12s}  {pct:.1f}%  entro [{bounds_lo[i]:.1f}, {bounds_hi[i]:.1f}]")

print()
print("Valutazione completata.")
