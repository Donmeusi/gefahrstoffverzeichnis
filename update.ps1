Start-Sleep -Seconds 2

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "data\backups"
if (-not (Test-Path -Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}

if (Test-Path -Path "data\gefahrstoffe.db") {
    Copy-Item -Path "data\gefahrstoffe.db" -Destination "$backupDir\gefahrstoffe_$timestamp.db"
} elseif (Test-Path -Path "gefahrstoffe.db") {
    Copy-Item -Path "gefahrstoffe.db" -Destination "$backupDir\gefahrstoffe_$timestamp.db"
}

# Branch wechseln falls angegeben (via Umgebungsvariable TARGET_BRANCH)
$targetBranch = $env:TARGET_BRANCH
if ($targetBranch) {
    git fetch
    git checkout $targetBranch
}

git pull

& .\venv\Scripts\python.exe -m pip install -r requirements.txt
$env:FLASK_APP="main.py"
& .\venv\Scripts\flask.exe db upgrade

# Beende alte Python-Prozesse, die main.py oder run_prod.py ausführen
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*main.py*" -or $_.CommandLine -like "*run_prod.py*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

Start-Process -FilePath ".\venv\Scripts\python.exe" -ArgumentList "main.py"
