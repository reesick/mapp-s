<#
  One-shot local runner. Everything (venv, pip cache, HF models, temp) stays on D:.

  .\launch.ps1              # SIFT mode: setup on first run, then start app
  .\launch.ps1 -Dino        # also install torch(CUDA)+transformers+faiss, run with DINOv2 shortlist
  .\launch.ps1 -Eval        # run evaluate.py instead of the web app
  .\launch.ps1 -Reinstall   # wipe .venv and rebuild
  .\launch.ps1 -Port 5001
  .\launch.ps1 -Dataset VIT_IMAGES   # use another map folder (default PCCOE_IMAGES)
#>
param(
    [switch]$Dino,
    [switch]$Eval,
    [switch]$Reinstall,
    [int]$Port = 5000,
    [string]$Dataset = 'PCCOE_IMAGES'
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
Set-Location -LiteralPath $Root

if ($Root -notlike 'D:*') { Write-Warning "Project is not on D: ($Root). Caches will still go under it." }

# Keep every cache/temp on D: (C: is full)
$Cache = Join-Path $Root '.cache'
$dirs = @('pip', 'hf', 'torch', 'tmp') | ForEach-Object { New-Item -ItemType Directory -Force -Path (Join-Path $Cache $_) }
$env:PIP_CACHE_DIR            = Join-Path $Cache 'pip'
$env:HF_HOME                  = Join-Path $Cache 'hf'
$env:TORCH_HOME               = Join-Path $Cache 'torch'
$env:TEMP                     = Join-Path $Cache 'tmp'
$env:TMP                      = $env:TEMP
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
$env:PYTHONDONTWRITEBYTECODE  = '1'

$Venv   = Join-Path $Root '.venv'
$Py     = Join-Path $Venv 'Scripts\python.exe'
$Marker = Join-Path $Venv '.deps-ok'
$DinoMarker = Join-Path $Venv '.dino-ok'

function Run([string]$exe, [string[]]$a) {
    & $exe @a
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $exe $($a -join ' ')" }
}

if ($Reinstall -and (Test-Path $Venv)) {
    Write-Host '==> Removing old .venv'
    Remove-Item -Recurse -Force $Venv
}

# 1. venv
if (-not (Test-Path $Py)) {
    Write-Host '==> Creating venv on D: (Python 3.11)'
    $created = $false
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.11 -m venv $Venv
        $created = ($LASTEXITCODE -eq 0)
    }
    if (-not $created) {
        Run 'python' @('-m', 'venv', $Venv)
    }
}

# 2. base deps (Flask, OpenCV SIFT, numpy, Pillow)
if (-not (Test-Path $Marker)) {
    Write-Host '==> Installing base requirements'
    Run $Py @('-m', 'pip', 'install', '--upgrade', 'pip')
    Run $Py @('-m', 'pip', 'install', '-r', (Join-Path $Root 'requirements.txt'))
    New-Item -ItemType File -Force -Path $Marker | Out-Null
}

# 3. optional DINOv2 stack (RTX 4050 -> CUDA build of torch)
if ($Dino) {
    if (-not (Test-Path $DinoMarker)) {
        Write-Host '==> Installing torch (CUDA 12.4) + transformers + faiss-cpu  (~3 GB, goes to D:)'
        Run $Py @('-m', 'pip', 'install', 'torch', '--index-url', 'https://download.pytorch.org/whl/cu124')
        Run $Py @('-m', 'pip', 'install', 'transformers', 'faiss-cpu')
        New-Item -ItemType File -Force -Path $DinoMarker | Out-Null
    }
    $env:USE_DINO = '1'
    Write-Host '==> DINO mode on (model weights download to .cache\hf on first run)'
} else {
    $env:USE_DINO = '0'
}
$env:DATASET_DIR = (Join-Path $Root $Dataset)

# 4. sanity check
Run $Py @('-c', 'import cv2, flask, numpy, PIL; print(chr(100)+chr(101)+chr(112)+chr(115)+chr(32)+chr(79)+chr(75))')
$imgs = (Get-ChildItem -Recurse -File (Join-Path $Root $Dataset) -Include *.jpg, *.jpeg, *.png -ErrorAction SilentlyContinue | Measure-Object).Count
if ($imgs -eq 0) { throw "No images found in $Dataset" }
Write-Host "==> $imgs reference images in $Dataset"

# 5. go
$env:PORT = "$Port"
$env:HOST = '127.0.0.1'
if ($Eval) {
    Write-Host '==> Running evaluate.py'
    Run $Py @('evaluate.py')
} else {
    Write-Host "==> Starting app: http://127.0.0.1:$Port   (Ctrl+C to stop)"
    Start-Job { Start-Sleep 4; Start-Process "http://127.0.0.1:$using:Port" } | Out-Null
    & $Py app.py
}
