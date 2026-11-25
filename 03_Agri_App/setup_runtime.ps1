# One-time set-up of the app's own Python in runtime\ (called by run_app.bat when no ready Python is found).
#  - downloads the official "embeddable" Python from python.org (no installer, no admin rights, nothing in the
#    registry: everything stays inside the app folder)
#  - adds pip and the app's libraries (runtime_requirements.txt)
# Needs internet once. Afterwards the whole app folder (with runtime\) can be copied to any Windows PC - even one
# with no internet and nothing installed - and run_app.bat starts it from there.
param([string]$Root = $PSScriptRoot)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"            # much faster downloads in Windows PowerShell 5.1
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$rt   = Join-Path $Root "runtime"
$logs = Join-Path $Root "03_logs"
New-Item -ItemType Directory -Force $logs | Out-Null
$log  = Join-Path $logs "setup_runtime.log"
function Say($text) { Write-Host $text; Add-Content -Path $log -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $text" }

Say "Setting up the app's own Python in $rt"
if (Test-Path $rt) { Remove-Item -Recurse -Force $rt }       # a half-finished earlier try
New-Item -ItemType Directory -Force $rt | Out-Null

# 1. embeddable Python (first version found on python.org)
$tmp = Join-Path $env:TEMP "agri_app_setup"
New-Item -ItemType Directory -Force $tmp | Out-Null
$zip = Join-Path $tmp "python-embed.zip"
$got = $null
foreach ($v in @("3.13.9", "3.13.7", "3.12.10")) {
    $url = "https://www.python.org/ftp/python/$v/python-$v-embed-amd64.zip"
    try {
        Say "Downloading Python $v ..."
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
        $got = $v
        break
    } catch { Say "  not available ($($_.Exception.Message))" }
}
if (-not $got) { throw "Could not download Python from python.org - is the PC connected to the internet?" }
Expand-Archive -Path $zip -DestinationPath $rt -Force

# 2. let it use site-packages and find the app folder (..\ = the folder with app.py / bootstrap.py)
$pth = Get-ChildItem $rt -Filter "python*._pth" | Select-Object -First 1
$lines = Get-Content $pth.FullName | ForEach-Object { if ($_ -match "^#\s*import site") { "import site" } else { $_ } }
$lines += "Lib\site-packages"
$lines += ".."
Set-Content -Path $pth.FullName -Value $lines -Encoding ASCII
New-Item -ItemType Directory -Force (Join-Path $rt "Lib\site-packages") | Out-Null

# 3. pip, then the app's libraries
$py = Join-Path $rt "python.exe"
$getpip = Join-Path $tmp "get-pip.py"
Say "Downloading pip ..."
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getpip -UseBasicParsing
& $py $getpip --no-warn-script-location 2>&1 | Add-Content -Path $log
if ($LASTEXITCODE -ne 0) { throw "pip could not be set up (see $log)" }
Say "Downloading the app's libraries (PySide6, pandas, ...) - a few minutes ..."
& $py -m pip install --no-warn-script-location -r (Join-Path $Root "runtime_requirements.txt") 2>&1 | Add-Content -Path $log
if ($LASTEXITCODE -ne 0) { throw "The libraries could not be installed (see $log)" }

# 4. check, and mark the runtime ready
& $py -c "import PySide6.QtWidgets, PySide6.QtPdf, pandas, numpy, openpyxl, lxml, yaml, pyodbc, joblib, win32com.client; print('ok')" 2>&1 | Add-Content -Path $log
if ($LASTEXITCODE -ne 0) { throw "The new Python cannot load the app's libraries (see $log)" }
Set-Content -Path (Join-Path $rt "READY.txt") -Value "Python $got, set up $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue

# 5. Access databases (.mdb / .accdb schedules) need Microsoft's Access driver - not part of Windows
$drv = Get-OdbcDriver -Platform "64-bit" -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "Microsoft Access Driver*" }
if (-not $drv) {
    Say "NOTE: this PC has no 64-bit 'Microsoft Access Driver (*.mdb, *.accdb)'. The app runs; only importing .mdb /"
    Say "      .accdb files needs it - install Microsoft's 'Access Database Engine 2016 Redistributable (x64)'."
}
Say "Done - the app's Python is ready (Python $got)."
