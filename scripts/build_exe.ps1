$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    py -3.14 -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller `
    --onefile `
    --console `
    --name ShuXiangBaiDuCrawler `
    --collect-all bs4 `
    --collect-all openpyxl `
    --collect-all tqdm `
    --hidden-import lxml `
    --hidden-import lxml.etree `
    --hidden-import lxml.html `
    bupt_library_crawler\launcher.py

Write-Host "Built: $ProjectRoot\dist\ShuXiangBaiDuCrawler.exe"

