# PowerShell Environment Verification Script for Bosch Incident Zero

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " Bosch Incident Zero - PowerShell Environment Diagnostics" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

# 1. Python Check
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK]   Python Runtime           : $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Python Runtime           : Python not found on PATH" -ForegroundColor Red
}

# 2. Docker Check
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK]   Docker Daemon            : Docker daemon is running" -ForegroundColor Green
    } else {
        Write-Host "[WARN] Docker Daemon            : Docker daemon is NOT running" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[WARN] Docker Daemon            : Docker CLI error" -ForegroundColor Yellow
}

# 3. Port Checks
$ports = @{
    "Jaeger (16686)"        = 16686
    "Prometheus (9090)"     = 9090
    "OpenSearch (9200)"     = 9200
    "Envoy Frontend (8080)" = 8080
    "Flagd (8013)"          = 8013
}

$activePorts = 0
foreach ($service in $ports.Keys) {
    $p = $ports[$service]
    $tcp = Test-NetConnection -ComputerName 127.0.0.1 -Port $p -WarningAction SilentlyContinue
    if ($tcp.TcpTestSucceeded) {
        Write-Host "[OK]   $service : Reachable" -ForegroundColor Green
        $activePorts++
    } else {
        Write-Host "[INFO] $service : Not listening" -ForegroundColor Gray
    }
}

Write-Host "----------------------------------------------------------------------"
if ($activePorts -gt 0) {
    Write-Host "OpenTelemetry Demo status: $activePorts endpoints reachable." -ForegroundColor Green
} else {
    Write-Host "OpenTelemetry Demo is not currently running." -ForegroundColor Yellow
}

# 4. Kill-Switch Check
$sentinelExists = Test-Path -Path ".\.kill_switch"
$envKillSwitch = $env:KILL_SWITCH_ENABLED
if ($sentinelExists -or ($envKillSwitch -eq "true")) {
    Write-Host "[WARN] Emergency Kill-Switch   : ENGAGED (Autonomous actions BLOCKED)" -ForegroundColor Red
} else {
    Write-Host "[OK]   Emergency Kill-Switch   : Disengaged (Normal Operation)" -ForegroundColor Green
}
Write-Host "======================================================================" -ForegroundColor Cyan
