@echo off
REM ==========================================================================
REM CF_FSNN Simulator launcher (conda).  Double-click to run.
REM  - First run: creates the `cf_sim` conda env from environment.yml (~minutes).
REM  - Applies the OMP #15 fix, then launches the GUI.
REM Requires Miniconda/Anaconda on PATH.  Optional arg: a champion .pt path.
REM (pip fallback for machines WITH the MSVC redistributable: requirements-sim.txt)
REM ==========================================================================
setlocal
cd /d "%~dp0"

where conda >nul 2>&1 || (echo Miniconda/Anaconda non trovato nel PATH. Installa Miniconda. & pause & exit /b 1)

conda env list | findstr /r /c:"^cf_sim " >nul 2>&1
if errorlevel 1 (
    echo [setup] Creating conda env cf_sim from environment.yml ^(alcuni minuti^)...
    call conda env create -f environment.yml || (echo conda env create fallito. & pause & exit /b 1)
)

REM OMP Error #15: torch/MKL use Intel iomp5; a redundant LLVM libomp.dll clashes -> disable it.
for /f "delims=" %%P in ('conda run -n cf_sim python -c "import sys,os;print(os.path.join(sys.prefix,'Library','bin','libomp.dll'))"') do set "OMPDLL=%%P"
if exist "%OMPDLL%" (
    echo [fix] disabling redundant libomp.dll ^(OMP #15^)...
    ren "%OMPDLL%" libomp.dll.disabled
)

call conda run -n cf_sim python scripts\run_simulator.py %*
endlocal
