@echo off
cd /d "D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN"
python train.py --n_train 5 --n_val 2 --epochs 2 --batch 2 --seq_len 20
echo.
echo --- FINE (premi un tasto per chiudere) ---
pause
