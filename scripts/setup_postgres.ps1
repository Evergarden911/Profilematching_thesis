# Setup PostgreSQL for Pramita SDM DSS (Windows + PostgreSQL 18)
# Run from project root in PowerShell:
#   .\scripts\setup_postgres.ps1
# Reset forgotten postgres password (requires Administrator):
#   .\scripts\setup_postgres.ps1 -ResetPassword

param(
    [string]$Password,
    [switch]$ResetPassword,
    [switch]$SkipCreateDatabase,
    [switch]$SkipCreateTables
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$EnvFile = Join-Path $ProjectRoot ".env"
$PgBin = "C:\Program Files\PostgreSQL\18\bin"
$PgHba = "C:\Program Files\PostgreSQL\18\data\pg_hba.conf"
$ServiceName = "postgresql-x64-18"
$DbName = "sdm_dss"
$DbUser = "postgres"

function Write-Step([string]$msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Encode-UrlPassword([string]$plain) { [uri]::EscapeDataString($plain) }

function Test-PostgresService {
    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $svc) {
        throw "Service '$ServiceName' not found. Install PostgreSQL 18 or adjust `$ServiceName in this script."
    }
    if ($svc.Status -ne "Running") {
        Write-Step "Starting PostgreSQL service..."
        Start-Service $ServiceName
    }
    Write-Host "PostgreSQL service: $($svc.DisplayName) — Running"
}

function Reset-PostgresPassword {
    param([string]$NewPassword)

    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
    if (-not $isAdmin) {
        throw "Password reset requires Administrator PowerShell. Right-click PowerShell -> Run as administrator."
    }
    if (-not (Test-Path $PgHba)) {
        throw "pg_hba.conf not found at: $PgHba"
    }

    Write-Step "Resetting postgres password (temporary trust auth on localhost)..."

    $backup = "$PgHba.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Copy-Item $PgHba $backup -Force
    Write-Host "Backup: $backup"

    $lines = Get-Content $PgHba
    $newLines = foreach ($line in $lines) {
        if ($line -match '^\s*(local|host)\s+all\s+all\s+' -and $line -notmatch 'replication') {
            $line -replace 'scram-sha-256', 'trust'
        } else { $line }
    }
    Set-Content -Path $PgHba -Value $newLines -Encoding UTF8

    Restart-Service $ServiceName -Force
    Start-Sleep -Seconds 2

    $escaped = $NewPassword -replace "'", "''"
    $sql = "ALTER USER postgres PASSWORD '$escaped';"
    & "$PgBin\psql.exe" -U $DbUser -h localhost -d postgres -c $sql

    Copy-Item $backup $PgHba -Force
    Restart-Service $ServiceName -Force
    Start-Sleep -Seconds 2

    Write-Host "Password reset complete. pg_hba.conf restored." -ForegroundColor Green
}

function Update-EnvFile {
    param([string]$PlainPassword, [string]$Database, [bool]$InitTables)

    if (-not (Test-Path $EnvFile)) {
        throw ".env not found at $EnvFile"
    }

    $encoded = Encode-UrlPassword $PlainPassword
    $url = "postgresql+psycopg2://${DbUser}:${encoded}@localhost:5432/${Database}"
    $initFlag = if ($InitTables) { "true" } else { "false" }

    $content = Get-Content $EnvFile -Raw
    if ($content -match '(?m)^DATABASE_URL=') {
        $content = $content -replace '(?m)^DATABASE_URL=.*$', "DATABASE_URL=$url"
    } else {
        $content += "`nDATABASE_URL=$url`n"
    }
    if ($content -match '(?m)^DB_INIT_ON_STARTUP=') {
        $content = $content -replace '(?m)^DB_INIT_ON_STARTUP=.*$', "DB_INIT_ON_STARTUP=$initFlag"
    } else {
        $content += "`nDB_INIT_ON_STARTUP=$initFlag`n"
    }
    Set-Content -Path $EnvFile -Value $content.TrimEnd() -Encoding UTF8 -NoNewline
    Add-Content -Path $EnvFile -Value ""
    Write-Host ".env updated (DATABASE_URL -> ...@localhost:5432/$Database)"
}

function Invoke-Psql {
    param([string]$PlainPassword, [string]$Args)
    $env:PGPASSWORD = $PlainPassword
    try {
        & "$PgBin\psql.exe" @Args
        if ($LASTEXITCODE -ne 0) { throw "psql failed (exit $LASTEXITCODE)" }
    } finally {
        Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    }
}

function Test-PythonConnection {
    Push-Location $ProjectRoot
    try {
        & (Join-Path $ProjectRoot ".venv\Scripts\python.exe") "scripts\check_db.py"
        if ($LASTEXITCODE -ne 0) { throw "Connection test failed" }
    } finally {
        Pop-Location
    }
}

# --- Main ---

Write-Host "Pramita SDM DSS — PostgreSQL setup" -ForegroundColor Yellow
Set-Location $ProjectRoot

if (-not (Test-Path $PgBin)) {
    throw "PostgreSQL bin not found at $PgBin. Install PostgreSQL 18 or edit paths in setup_postgres.ps1."
}

Test-PostgresService

if ($ResetPassword) {
    if (-not $Password) {
        $sec = Read-Host "Enter NEW postgres password" -AsSecureString
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
        try { $Password = [Runtime.InteropServices.Marshal]::PtrToStringAuto($ptr) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    }
    Reset-PostgresPassword -NewPassword $Password
}

if (-not $Password) {
    $sec = Read-Host "Enter postgres password" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    try { $Password = [Runtime.InteropServices.Marshal]::PtrToStringAuto($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

Write-Step "Testing connection to database 'postgres'..."
$env:PGPASSWORD = $Password
try {
    & "$PgBin\psql.exe" -U $DbUser -h localhost -d postgres -c "SELECT 1 AS ok;" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Authentication failed" }
    Write-Host "psql connection OK"
} catch {
    throw @"
Could not connect with that password.

If you forgot the password, run as Administrator:
  .\scripts\setup_postgres.ps1 -ResetPassword

Then run this script again without -ResetPassword.
"@
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}

if (-not $SkipCreateDatabase) {
    Write-Step "Creating database '$DbName' (if missing)..."
    $env:PGPASSWORD = $Password
    try {
        $exists = & "$PgBin\psql.exe" -U $DbUser -h localhost -d postgres -tAc `
            "SELECT 1 FROM pg_database WHERE datname = '$DbName';"
        if ($exists.Trim() -ne "1") {
            & "$PgBin\psql.exe" -U $DbUser -h localhost -d postgres -c `
                "CREATE DATABASE $DbName ENCODING 'UTF8' TEMPLATE template0;"
            Write-Host "Database '$DbName' created."
        } else {
            Write-Host "Database '$DbName' already exists."
        }
    } finally {
        Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    }
}

Write-Step "Writing .env..."
Update-EnvFile -PlainPassword $Password -Database $DbName -InitTables:(-not $SkipCreateTables)

Write-Step "Testing Python/SQLAlchemy connection..."
Test-PythonConnection

if (-not $SkipCreateTables) {
    Write-Step "Creating application tables..."
    & (Join-Path $ProjectRoot ".venv\Scripts\python.exe") "scripts\init_tables.py"
    if ($LASTEXITCODE -ne 0) { throw "init_tables.py failed" }
}

Write-Host "`nSetup complete." -ForegroundColor Green
Write-Host @"

Next steps:
  1. Start API:  .\.venv\Scripts\uvicorn.exe backend.main:app --reload --host 127.0.0.1 --port 8000
  2. Open UI:    http://127.0.0.1:8000/
  3. Health:     http://127.0.0.1:8000/health

DB_INIT_ON_STARTUP is true — tables sync on each app start.
To disable: set DB_INIT_ON_STARTUP=false in .env

"@
