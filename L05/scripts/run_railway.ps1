param(
  [Parameter(Mandatory = $false)]
  [string]$ApiKey = $env:AI_DEVS_4_API_KEY,

  [Parameter(Mandatory = $false)]
  [int]$Port = 8000
)

if (-not $ApiKey) {
  Write-Error "Brak API key. Podaj -ApiKey lub ustaw AI_DEVS_4_API_KEY."
  exit 2
}

$rootDir = Split-Path -Path $PSScriptRoot -Parent
$py = Join-Path $rootDir "../.venv/Scripts/python.exe"
$logFile = Join-Path $rootDir "logs/railway_requests.log"

& $py -m pip install -r (Join-Path $rootDir "requirements.txt")
& $py (Join-Path $rootDir "scripts/railway_client.py") --apikey $ApiKey --auto --route x-01 --log $logFile

Select-String -Path $logFile -Pattern "FLG|COUNTRYROADS" | ForEach-Object { $_.Line }

Write-Host ""
Write-Host "Aby uruchomic UI logow:"
Write-Host "  $py $(Join-Path $rootDir 'scripts/serve_ui.py') --port $Port"
Write-Host "  http://localhost:$Port/ui/"
