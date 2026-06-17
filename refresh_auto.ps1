# Rafraîchissement automatique du dashboard carburant (export API -> git push).
# Lancé par la tâche planifiée Windows « MAJ Dashboard Carburant » (hebdomadaire).
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Dossier du dépôt = dossier de ce script
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repo

# Interpréteur Python (venv du projet contenant 'requests')
$py = "D:\ehcvm3 phase2\banque epreuves\env\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

# Journal
$logDir = Join-Path $repo "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$log = Join-Path $logDir "refresh.log"
function Log($m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $m" | Tee-Object -FilePath $log -Append }

Log "=== Démarrage rafraîchissement ==="
try {
    & $py "export_carburant.py" 2>&1 | Tee-Object -FilePath $log -Append

    & git add data/carburant.json
    & git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) {
        Log "Aucun changement de données — rien à pousser."
    } else {
        $stamp = Get-Date -Format "yyyy-MM-dd HH:mm"
        & git commit -m "MAJ auto données carburant ($stamp)" | Out-Null
        & git push origin main 2>&1 | Tee-Object -FilePath $log -Append
        Log "Données mises à jour et poussées."
    }
} catch {
    Log "ERREUR : $_"
    exit 1
}
Log "=== Fin ==="
