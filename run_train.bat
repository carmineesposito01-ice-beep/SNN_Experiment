@echo off
cd /d "D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN"
echo ============================================================
echo  CF_FSNN -- Training overnight (1000 traj / 20 epoche)
echo  ~2.58 s/batch  ~8.5 h totali stimati su CPU
echo ============================================================
echo.
python train.py ^
    --n_train 1000 ^
    --n_val   100  ^
    --epochs  20   ^
    --batch   32   ^
    --seq_len 100
echo.
echo ============================================================
echo  TRAINING COMPLETATO
echo ============================================================
pause
