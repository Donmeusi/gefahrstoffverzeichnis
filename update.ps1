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
    # Nur Zeichen, die in einem Branch-Namen vorkommen koennen; sonst wird ein
    # Wert wie "-f" von git als Option gelesen.
    if ($targetBranch -notmatch '^[A-Za-z0-9._/-]+$' -or $targetBranch.StartsWith('-')) {
        Write-Error "Ungueltiger Branch-Name: $targetBranch"
        exit 1
    }
    git -c protocol.ext.allow=never fetch
    git -c protocol.ext.allow=never checkout $targetBranch
}

git -c protocol.ext.allow=never pull

& .\venv\Scripts\python.exe -m pip install --require-hashes -r requirements.txt
$env:FLASK_APP="main.py"
& .\venv\Scripts\flask.exe db upgrade

# Nur Prozesse beenden, die aus genau diesem venv gestartet wurden. Vorher
# genuegte "main.py" in der Kommandozeile, um einen fremden Python-Dienst
# auf demselben Rechner abzuschiessen.
$venvPython = (Resolve-Path ".\venv\Scripts\python.exe").Path
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ExecutablePath -and $_.ExecutablePath -ieq $venvPython } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

# run_prod.py statt main.py: main.py startet den Werkzeug-Entwicklungsserver,
# der nicht fuer den Dauerbetrieb gedacht ist.
Start-Process -FilePath ".\venv\Scripts\python.exe" -ArgumentList "run_prod.py"
