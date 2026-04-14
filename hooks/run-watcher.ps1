# ToolMaster Global Watcher - Windows background daemon launcher
#
# Usage:
#   .\hooks\run-watcher.ps1 start
#   .\hooks\run-watcher.ps1 stop
#   .\hooks\run-watcher.ps1 status
#
# Uses pythonw.exe for true console-less detachment that survives terminal exit.
# Reads OPENROUTER_API_KEY from <repo>\.env if present, or from current env.

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "status", "restart")]
    [string]$Action = "start"
)

$ErrorActionPreference = "Stop"

$RepoDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$StateDir = if ($env:TOOLMASTER_HOME) { $env:TOOLMASTER_HOME } else { Join-Path $env:USERPROFILE ".toolmaster" }
$PidFile = Join-Path $StateDir "watcher.pid"
$LogFile = Join-Path $StateDir "watcher.log"

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

function Load-DotEnv {
    $envFile = Join-Path $RepoDir ".env"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)\s*$') {
                $k = $matches[1]
                $v = $matches[2].Trim('"').Trim("'")
                if ($v -and -not [string]::IsNullOrWhiteSpace($v)) {
                    Set-Item -Path "Env:$k" -Value $v
                }
            }
        }
    }
}

function Get-DaemonPid {
    if (Test-Path $PidFile) {
        $p = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($p -and (Get-Process -Id $p -ErrorAction SilentlyContinue)) {
            return [int]$p
        }
    }
    return $null
}

function Start-Watcher {
    $existing = Get-DaemonPid
    if ($existing) {
        Write-Host "Watcher already running (PID $existing)"
        return
    }

    Load-DotEnv
    if (-not $env:CLAUDE_DIR) { $env:CLAUDE_DIR = "C:/Claude" }

    if (-not $env:OPENROUTER_API_KEY) {
        Write-Host "WARNING: OPENROUTER_API_KEY is not set - scout layer will be inert."
        Write-Host "         Set it in $RepoDir\.env or export it before starting."
    }

    # pythonw.exe = console-less Python, fully detaches from this shell
    $pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
    if (-not $pythonw) {
        $pythonw = (Get-Command python.exe).Source -replace 'python\.exe$', 'pythonw.exe'
    }

    $proc = Start-Process -FilePath $pythonw `
        -ArgumentList "-m", "toolmaster", "watch", "--interval", "30" `
        -WorkingDirectory $RepoDir `
        -RedirectStandardOutput $LogFile `
        -RedirectStandardError "$LogFile.err" `
        -WindowStyle Hidden `
        -PassThru

    $proc.Id | Out-File -FilePath $PidFile -Encoding ascii -NoNewline
    Write-Host "Watcher started (PID $($proc.Id))"
    Write-Host "Repo:  $RepoDir"
    Write-Host "State: $StateDir"
    Write-Host "Log:   $LogFile"
}

function Stop-Watcher {
    $p = Get-DaemonPid
    if ($p) {
        Stop-Process -Id $p -Force
        Remove-Item $PidFile -ErrorAction SilentlyContinue
        Write-Host "Watcher stopped (PID $p)"
    } else {
        if (Test-Path $PidFile) { Remove-Item $PidFile }
        Write-Host "Watcher is not running"
    }
}

function Get-Status {
    $p = Get-DaemonPid
    if ($p) {
        Write-Host "Watcher running (PID $p)"
        Write-Host "Log: $LogFile"
        if (Test-Path $LogFile) {
            Write-Host ""
            Write-Host "Last 10 lines:"
            Get-Content $LogFile -Tail 10
        }
    } else {
        Write-Host "Watcher is not running"
    }
}

switch ($Action) {
    "start"   { Start-Watcher }
    "stop"    { Stop-Watcher }
    "status"  { Get-Status }
    "restart" { Stop-Watcher; Start-Sleep -Seconds 1; Start-Watcher }
}
