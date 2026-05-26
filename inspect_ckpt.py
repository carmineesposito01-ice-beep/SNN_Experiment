import torch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

paths = [
    ('checkpoints/best.pt',      'BEST checkpoint'),
    ('checkpoints/epoch_010.pt', 'Epoca 10'),
    ('checkpoints/epoch_020.pt', 'Epoca 20'),
]

for path, label in paths:
    ck = torch.load(path, map_location='cpu')
    print(f"=== {label} ===")
    print(f"  Epoca    : {ck['epoch']}")
    print(f"  val_loss : {ck['val_loss']:.6f}")
    print()

# Analisi parametri del modello best
print("=== Parametri modello (best.pt) ===")
ck_best = torch.load('checkpoints/best.pt', map_location='cpu')
sd = ck_best['model_state']
for k, v in sd.items():
    print(f"  {k:45s}  shape={str(v.shape):25s}  mean={v.float().mean().item():+.4f}  std={v.float().std().item():.4f}")
