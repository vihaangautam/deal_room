<#
.SYNOPSIS
    Brings the Lilkis Deal Room up from a cold laptop, ready to demo.

.DESCRIPTION
    Starts Docker if it is down, waits for Postgres and storage to be
    healthy, applies any pending migration, repairs the seeded files,
    starts the API and the frontend, and then proves it works by signing
    in before telling you it is ready.

    Safe to run twice. Anything already up is left alone.

    The seed step is not optional housekeeping: S3Mock keeps uploaded
    files in a container temp directory and loses them on restart, while
    Postgres keeps its rows on a named volume. After any reboot every
    document still lists and none of them download. Re-seeding rewrites
    the missing files and leaves the rows alone.

.PARAMETER Stop
    Stops the API, the frontend and the containers.

.PARAMETER Reset
    Destroys the database and storage and rebuilds from the seed. Use
    when the demo data has been edited into a mess.

.EXAMPLE
    .\start.ps1
    .\start.ps1 -Reset
    .\start.ps1 -Stop
#>
[CmdletBinding()]
param(
    [switch]$Stop,
    [switch]$Reset
)

$ErrorActionPreference = 'Stop'
$root     = $PSScriptRoot
$backend  = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$python   = Join-Path $backend '.venv\Scripts\python.exe'
$logs     = Join-Path $root 'logs'

$API_PORT = 8002
$WEB_PORT = 5173
$APP_URL  = "http://localhost:$WEB_PORT"
$API_URL  = "http://localhost:$API_PORT"

function Write-Step { param($Message) Write-Host "  $Message" -ForegroundColor Cyan }
function Write-Ok   { param($Message) Write-Host "  $Message" -ForegroundColor Green }
function Write-Warn { param($Message) Write-Host "  $Message" -ForegroundColor Yellow }
function Write-Bad  { param($Message) Write-Host "  $Message" -ForegroundColor Red }

<#
    Every external command goes through here.

    PowerShell 5.1 wraps a native program's stderr in ErrorRecords and
    sets $? to $false even when the program exited 0 — and `docker
    compose` writes its ordinary progress to stderr. With
    $ErrorActionPreference = 'Stop' that turns a successful `docker
    compose up` into a terminating error, which is exactly how the first
    version of this script failed. Success is judged by $LASTEXITCODE
    instead, which is the only honest signal.
#>
function Invoke-Native {
    param([Parameter(Mandatory)][scriptblock]$Command)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & $Command 2>&1 | ForEach-Object { "$_" }
        return [pscustomobject]@{ Ok = ($LASTEXITCODE -eq 0); Output = $output }
    } finally {
        $ErrorActionPreference = $previous
    }
}

function Test-Port {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $conn
}

function Stop-Port {
    param([int]$Port, [string]$Label)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($null -eq $conn) { return }
    # $pid is an automatic variable in PowerShell (this process), so the
    # loop variable cannot be called that.
    foreach ($procId in ($conn | Select-Object -ExpandProperty OwningProcess -Unique)) {
        try {
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Write-Ok "Stopped $Label (pid $procId)"
        } catch {
            Write-Warn "Could not stop $Label (pid $procId): $($_.Exception.Message)"
        }
    }
}

# A connection refused is an expected answer while waiting, not an error.
function Test-Url {
    param([string]$Url)
    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Wait-For {
    param(
        [scriptblock]$Condition,
        [string]$What,
        [int]$TimeoutSeconds = 180
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (& $Condition) { return $true }
        Start-Sleep -Seconds 2
    }
    Write-Bad "Gave up waiting for $What after $TimeoutSeconds seconds."
    return $false
}

# ─── stop ────────────────────────────────────────────────────────────────
if ($Stop) {
    Write-Host ""
    Write-Host "Stopping Lilkis Deal Room" -ForegroundColor White
    Stop-Port -Port $API_PORT -Label 'API'
    Stop-Port -Port $WEB_PORT -Label 'frontend'
    Push-Location $root
    $down = Invoke-Native { docker compose down }
    Pop-Location
    if ($down.Ok) { Write-Ok 'Containers stopped' } else { Write-Warn 'Containers were not running' }
    Write-Host ""
    Write-Host "Stopped. Docker Desktop is still running." -ForegroundColor White
    Write-Host ""
    return
}

Write-Host ""
Write-Host "Starting Lilkis Deal Room" -ForegroundColor White
Write-Host ""

if (-not (Test-Path $python)) {
    Write-Bad "No virtualenv at $python"
    Write-Bad 'Create it:  cd backend; python -m venv .venv; .\.venv\Scripts\pip install -e ".[dev]"'
    exit 1
}
if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
    Write-Bad 'No node_modules in frontend. Run:  cd frontend; npm install'
    exit 1
}
New-Item -ItemType Directory -Force -Path $logs | Out-Null

# ─── 1. Docker ───────────────────────────────────────────────────────────
Write-Step '1/5  Docker'
if (-not (Invoke-Native { docker ps }).Ok) {
    $desktop = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path $desktop)) {
        Write-Bad "Docker engine is down and Docker Desktop is not at $desktop"
        exit 1
    }
    Write-Warn 'Engine is down - starting Docker Desktop (takes a minute)'
    Start-Process $desktop
    # The engine answers long after the window appears, so poll the engine
    # rather than trusting the process to mean anything.
    $ready = Wait-For -What 'the Docker engine' -TimeoutSeconds 240 -Condition {
        return (Invoke-Native { docker ps }).Ok
    }
    if (-not $ready) {
        Write-Bad 'Docker never came up. Start Docker Desktop by hand, then run this again.'
        exit 1
    }
}
Write-Ok 'Engine ready'

# ─── 2. Containers ───────────────────────────────────────────────────────
Push-Location $root
try {
    if ($Reset) {
        Write-Step '2/5  Containers (resetting - this destroys the demo data)'
        Invoke-Native { docker compose down -v } | Out-Null
    } else {
        Write-Step '2/5  Containers'
    }
    $up = Invoke-Native { docker compose up -d }
    if (-not $up.Ok) {
        Write-Bad 'docker compose up failed:'
        $up.Output | Select-Object -Last 8 | ForEach-Object { Write-Bad "    $_" }
        exit 1
    }

    $healthy = Wait-For -What 'Postgres and storage' -TimeoutSeconds 120 -Condition {
        $pg = (Invoke-Native { docker inspect lilkis-postgres --format '{{.State.Health.Status}}' }).Output
        $s3 = (Invoke-Native { docker inspect lilkis-s3mock   --format '{{.State.Health.Status}}' }).Output
        return ("$pg" -eq 'healthy' -and "$s3" -eq 'healthy')
    }
    if (-not $healthy) {
        Write-Bad 'Containers did not become healthy. Check:  docker compose logs'
        exit 1
    }
    Write-Ok 'Postgres and storage healthy'
} finally {
    Pop-Location
}

# ─── 3. Schema and demo data ─────────────────────────────────────────────
Write-Step '3/5  Schema and demo data'
Push-Location $backend
try {
    $migrate = Invoke-Native { & $python -m alembic upgrade head }
    if (-not $migrate.Ok) {
        Write-Bad 'Migration failed:'
        $migrate.Output | Select-Object -Last 8 | ForEach-Object { Write-Bad "    $_" }
        exit 1
    }

    # Idempotent: seeds a fresh database, and on an existing one rewrites
    # any stored file lost when the containers restarted.
    $seed = Invoke-Native { & $python -m app.seed }
    if (-not $seed.Ok) {
        Write-Bad 'Seed failed:'
        $seed.Output | Select-Object -Last 8 | ForEach-Object { Write-Bad "    $_" }
        exit 1
    }
    $seed.Output | Where-Object { $_ -match 'Seeded|Restored' } | ForEach-Object {
        Write-Ok ($_ -replace '^\s+', '')
    }
    Write-Ok 'Database ready'
} finally {
    Pop-Location
}

# ─── 4. Servers ──────────────────────────────────────────────────────────
Write-Step '4/5  Servers'

if (Test-Port -Port $API_PORT) {
    # A process left from a previous run holds the port but points at a
    # database that no longer exists, so replace it rather than reuse it.
    Write-Warn "Port $API_PORT was in use - restarting the API"
    Stop-Port -Port $API_PORT -Label 'API'
    Start-Sleep -Seconds 2
}
Start-Process -FilePath $python `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--port', "$API_PORT" `
    -WorkingDirectory $backend `
    -RedirectStandardOutput (Join-Path $logs 'api.log') `
    -RedirectStandardError  (Join-Path $logs 'api.err.log') `
    -WindowStyle Hidden
$apiUp = Wait-For -What 'the API' -TimeoutSeconds 90 -Condition {
    try {
        $r = Invoke-RestMethod -Uri "$API_URL/health" -TimeoutSec 3
        return ($r.db -eq 'ok')
    } catch { return $false }
}
if (-not $apiUp) {
    Write-Bad 'API did not start. Last lines of logs\api.err.log:'
    Get-Content (Join-Path $logs 'api.err.log') -Tail 12 -ErrorAction SilentlyContinue |
        ForEach-Object { Write-Bad "    $_" }
    exit 1
}
Write-Ok "API on $API_URL"

if (-not (Test-Port -Port $WEB_PORT)) {
    Start-Process -FilePath 'cmd.exe' `
        -ArgumentList '/c', 'npm run dev' `
        -WorkingDirectory $frontend `
        -RedirectStandardOutput (Join-Path $logs 'web.log') `
        -RedirectStandardError  (Join-Path $logs 'web.err.log') `
        -WindowStyle Hidden
    # The first run after a dependency change re-optimises and is slow.
    $webUp = Wait-For -What 'the frontend' -TimeoutSeconds 180 -Condition { Test-Url $APP_URL }
    if (-not $webUp) {
        Write-Bad 'Frontend did not start. Last lines of logs\web.log:'
        Get-Content (Join-Path $logs 'web.log') -Tail 12 -ErrorAction SilentlyContinue |
            ForEach-Object { Write-Bad "    $_" }
        exit 1
    }
} else {
    Write-Warn "Port $WEB_PORT already in use - assuming that frontend is yours"
}
Write-Ok "Frontend on $APP_URL"

# ─── 5. Prove it actually works ──────────────────────────────────────────
# Everything above only establishes that something is listening. None of
# it says you can sign in, which is the only thing that matters when
# someone is watching.
Write-Step '5/5  Signing in to check'
try {
    $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    # The seed password, printed in README.md. Local demo data only.
    $login = Invoke-WebRequest -Uri "$API_URL/auth/login" -Method Post `
        -Body @{ username = 'samir@lilkis.in'; password = 'changeme123' } `
        -WebSession $session -UseBasicParsing -TimeoutSec 10
    if ($login.StatusCode -ne 204) { throw "login returned $($login.StatusCode)" }

    $deals = Invoke-RestMethod -Uri "$API_URL/deals" -WebSession $session -TimeoutSec 10
    $docs  = ($deals | Measure-Object -Property document_count -Sum).Sum
    Write-Ok "Signed in - $($deals.Count) deals, $docs documents"
} catch {
    Write-Bad "Sign-in check FAILED: $($_.Exception.Message)"
    Write-Bad 'Servers are up but the app is not usable. Try:  .\start.ps1 -Reset'
    exit 1
}

Write-Host ""
Write-Host "  Ready - $APP_URL" -ForegroundColor White
Write-Host ""
Write-Host "  samir@lilkis.in   admin, approver" -ForegroundColor Gray
Write-Host "  rohan@lilkis.in   member, no access to Borrower details" -ForegroundColor Gray
Write-Host "  meera@lilkis.in   member, view only except Bank documents" -ForegroundColor Gray
Write-Host "  password          changeme123" -ForegroundColor Gray
Write-Host ""
Write-Host "  Demo script: DEMO.md      Stop: .\start.ps1 -Stop" -ForegroundColor DarkGray
Write-Host ""
