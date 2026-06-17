"""
eval_report.py -- Valutazione quantitativa del modello CF_FSNN addestrato.
==========================================================================
Genera metriche dettagliate su dati di test mai visti durante il training,
piu' i grafici G5 (T_pred vs T_true) e G7 (violin parametri).

Uso:
    python eval_report.py --checkpoint checkpoints/<tag>/best_model.pt
    python eval_report.py --checkpoint checkpoints/<tag>/best_model.pt --n_test 500
"""

import argparse
import math
import os
import sys

import numpy as np
import torch
from torch.utils.data import DataLoader

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from config import (
    SEED, set_seed,
    NORM_S_MAX, NORM_V_MAX, NORM_DV_MAX, NORM_VL_MAX,
    LAMBDA_DATA, LAMBDA_PHYS, LAMBDA_OU, LAMBDA_BC,
    IDM2D_T1, IDM2D_T2,
    ACC_COOLNESS, ACC_AL_TAU,
    DT,
)
from core.network import CF_FSNN_Net
from data.generator import generate_dataset, print_dataset_stats
from train import CFDataset, pinn_loss, _forward_sequence_with_stats

# Assicura che il monkey-patch sia attivo
CF_FSNN_Net.forward_sequence_with_stats = _forward_sequence_with_stats


def main():
    parser = argparse.ArgumentParser(
        description='CF_FSNN Evaluation Report — test set + grafici G5/G7'
    )
    parser.add_argument('--checkpoint', type=str,
                        default=os.path.join(_HERE, 'checkpoints', 'run', 'best_model.pt'),
                        help='Percorso al best_model.pt da valutare')
    parser.add_argument('--n_test', type=int, default=200,
                        help='Numero di traiettorie di test da generare')
    parser.add_argument('--batch_size', type=int, default=32)
    parser.add_argument('--seq_len',    type=int, default=100)
    parser.add_argument('--out_dir',    type=str, default=None,
                        help='Cartella output grafici (default: accanto al checkpoint)')
    args = parser.parse_args()

    set_seed(SEED + 99)   # seed diverso da train/val

    # ── Determina cartella output ──────────────────────────────────
    if args.out_dir is None:
        args.out_dir = os.path.join(
            os.path.dirname(args.checkpoint), 'eval_plots'
        )
    os.makedirs(args.out_dir, exist_ok=True)

    # ── Carica modello ─────────────────────────────────────────────
    if not os.path.isfile(args.checkpoint):
        print(f"[ERRORE] Checkpoint non trovato: {args.checkpoint}")
        sys.exit(1)

    device = torch.device('cpu')
    model  = CF_FSNN_Net().to(device)
    ck     = torch.load(args.checkpoint, map_location=device, weights_only=False)
    model.load_state_dict(ck['model_state'])
    model.eval()
    print(f"[Modello] Caricato da epoca {ck['epoch']}"
          f"  |  val_loss_salvata={ck['val_loss']:.6f}\n")

    # ── Genera test set ────────────────────────────────────────────
    print(f"[Dataset] Generazione {args.n_test} traiettorie di test (seed={SEED+99})...")
    test_data = generate_dataset(args.n_test, base_seed=SEED + 99)
    print_dataset_stats(test_data, 'test')

    test_ds = CFDataset(test_data, seq_len=args.seq_len, stride=args.seq_len)
    test_dl = DataLoader(test_ds, batch_size=args.batch_size,
                         shuffle=False, num_workers=0)
    print(f"[Dataset] Finestre test: {len(test_ds)}  |  Batch: {len(test_dl)}\n")

    # ── Valutazione PINN loss ──────────────────────────────────────
    lam = (LAMBDA_DATA, LAMBDA_PHYS, LAMBDA_OU, LAMBDA_BC)

    all_losses  = {'total': [], 'data': [], 'phys': [], 'ou': [], 'bc': []}
    T_pred_list = []
    T_true_list = []
    param_list  = []

    with torch.no_grad():
        for x, y, mask in test_dl:
            x    = x.to(device)
            y    = y.to(device)
            mask = mask.to(device)

            _, comps, _, _ = pinn_loss(model, x, y, mask, *lam)  # R25: 4-tuple (params_seq added)
            all_losses['total'].append(comps['total'])
            for k in ['data', 'phys', 'ou', 'bc']:
                all_losses[k].append(comps[k])

            params_seq, _ = model.forward_sequence_with_stats(x)  # (B, T, 5)
            T_pred_list.append(params_seq[:, :, 1].cpu().numpy())
            T_true_list.append(y[:, :, 1].cpu().numpy())
            param_list.append(params_seq.cpu().numpy())

    # ── Statistiche loss ───────────────────────────────────────────
    print("=" * 62)
    print("  METRICHE PINN LOSS (test set -- mai visto in training)")
    print("=" * 62)
    for k in ['total', 'data', 'phys', 'ou', 'bc']:
        arr = np.array(all_losses[k])
        print(f"  {k:8s}  mean={arr.mean():.5f}  std={arr.std():.5f}"
              f"  min={arr.min():.5f}  max={arr.max():.5f}")

    # ── Analisi parametri predetti ────────────────────────────────
    pred_np    = np.concatenate(param_list,  axis=0)  # (N, T, 5)
    T_pred_arr = np.concatenate(T_pred_list).ravel()
    T_true_arr = np.concatenate(T_true_list).ravel()

    names_out  = ['v0 [m/s]', 'T [s]', 's0 [m]', 'a [m/s2]', 'b [m/s2]']
    bounds_lo  = [ 8.0, 0.5, 1.0, 0.3, 0.5]
    bounds_hi  = [45.0, 2.5, 5.0, 2.5, 3.0]

    print()
    print("=" * 62)
    print("  PARAMETRI ACC-IDM PREDETTI (media su tutte le finestre)")
    print("=" * 62)
    for i, name in enumerate(names_out):
        p   = pred_np[:, :, i].ravel()
        pct = np.mean((p >= bounds_lo[i]) & (p <= bounds_hi[i])) * 100
        print(f"  {name:12s}  mean={p.mean():.3f}  std={p.std():.3f}"
              f"  range=[{p.min():.3f}, {p.max():.3f}]"
              f"  entro_bounds={pct:.1f}%")

    # ── T_pred vs T_true ──────────────────────────────────────────
    mae_T  = np.mean(np.abs(T_pred_arr - T_true_arr))
    rmse_T = math.sqrt(np.mean((T_pred_arr - T_true_arr) ** 2))
    bias_T = np.mean(T_pred_arr - T_true_arr)

    print()
    print("=" * 62)
    print("  STIMA T (time-gap): predetto vs ground truth")
    print("=" * 62)
    print(f"  T_true   mean={T_true_arr.mean():.3f}  std={T_true_arr.std():.3f}"
          f"  range=[{T_true_arr.min():.3f}, {T_true_arr.max():.3f}]")
    print(f"  T_pred   mean={T_pred_arr.mean():.3f}  std={T_pred_arr.std():.3f}"
          f"  range=[{T_pred_arr.min():.3f}, {T_pred_arr.max():.3f}]")
    print(f"  MAE(T)   = {mae_T:.4f} s")
    print(f"  RMSE(T)  = {rmse_T:.4f} s")
    print(f"  Bias(T)  = {bias_T:+.4f} s  (positivo=sovrastima)")
    print(f"  Banda IDM-2d su T attesa: [{IDM2D_T1}, {IDM2D_T2}] s  (estensione stocastica Ch12.6)")

    # ── Grafici G5 e G7 ───────────────────────────────────────────
    param_samples = {
        'v0': pred_np[:, :, 0].ravel(),
        'T':  pred_np[:, :, 1].ravel(),
        's0': pred_np[:, :, 2].ravel(),
        'a':  pred_np[:, :, 3].ravel(),
        'b':  pred_np[:, :, 4].ravel(),
    }
    try:
        from utils.plot_diagnostics import plot_g5_T_scatter, plot_g7_violin_params
        plot_g5_T_scatter(
            T_pred_arr, T_true_arr,
            os.path.join(args.out_dir, 'G5_T_scatter.png')
        )
        plot_g7_violin_params(
            param_samples,
            os.path.join(args.out_dir, 'G7_violin_params.png')
        )
        print(f"\n[Grafici] Salvati in: {args.out_dir}")
    except Exception as e:
        print(f"\n[Grafici] Saltati: {e}")

    print("\n[Valutazione completata]")


if __name__ == '__main__':
    main()
