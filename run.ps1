param(
	[string]$ProjectDir = "."
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info($msg) { Write-Host "[INFO ] $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[ OK  ] $msg" -ForegroundColor Green }
function Write-Err($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

Push-Location $ProjectDir
try {
	Write-Info "Checking Docker..."
	$null = docker version | Out-Null

	Write-Info "Starting ClickHouse with docker compose..."
	docker compose up -d

	Write-Info "Waiting for ClickHouse to be healthy (HTTP 8123)..."
	$deadline = (Get-Date).AddMinutes(5)
	$ok = $false
	while ((Get-Date) -lt $deadline) {
		try {
			$r = Invoke-WebRequest -UseBasicParsing "http://localhost:8123/ping" -TimeoutSec 3
			if ($r.Content -match "Ok") { $ok = $true; break }
		} catch { Start-Sleep -Seconds 2 }
		Start-Sleep -Seconds 2
	}
	if (-not $ok) { throw "ClickHouse did not become ready on :8123 within timeout." }
	Write-Ok "ClickHouse is ready."

	Write-Info "Ensuring Python dependencies..."
	python -m pip install --upgrade pip
	python -m pip install -r requirements.txt

	Write-Info "Running ingestion..."
	python ingest.py ingest --cwd . --host localhost --port 8123 --username default --password "admin" --database default
	Write-Ok "Ingestion complete."

} catch {
	Write-Err $_.Exception.Message
	exit 1
} finally {
	Pop-Location
}

