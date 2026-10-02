# radius_eval B2: seed 43 -> seed 44 -> check -> restore sleep -> shutdown in 5 min
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'
$env:DATA_DIR = $PSScriptRoot
$env:PYTHONPATH = 'src'
$env:BUDGET_S = '999999'
powercfg /change standby-timeout-ac 0
& .venv\Scripts\python.exe src\radius_eval.py --seed 43 2>&1 | Tee-Object -FilePath radius_run.log -Append
& .venv\Scripts\python.exe src\radius_eval.py --seed 44 2>&1 | Tee-Object -FilePath radius_run.log -Append
& .venv\Scripts\python.exe src\radius_eval.py --check 2>&1 | Tee-Object -FilePath radius_run.log -Append
powercfg /change standby-timeout-ac 30
shutdown /s /t 300
