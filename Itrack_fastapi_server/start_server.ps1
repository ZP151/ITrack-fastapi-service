# ====================================
# ITrack FastAPI Server One-Click Startup Script
# ====================================
#
# Usage Examples:
#   .\start_server.ps1                    # Normal startup
#   .\start_server.ps1 -Clean             # Clean virtual environment and restart
#   .\start_server.ps1 -Dev               # Development mode with hot reload
#   .\start_server.ps1 -ForceInstall      # Force reinstall all dependencies
#   .\start_server.ps1 -Port 9000         # Use custom port
#   .\start_server.ps1 -Dev -Port 9000    # Development mode with custom port
# ====================================

param(
    [switch]$Clean,                       # Clean and recreate virtual environment
    [switch]$Dev,                         # Development mode with hot reload
    [switch]$ForceInstall,                # Force reinstall dependencies
    [int]$Port = 8000,                    # Server port, default 8000
    [string]$ServerHost = "0.0.0.0"       # Server host, default allows external access
)

# Set error handling
$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = $PSScriptRoot
Set-Location $ScriptDir

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "ITrack FastAPI Server Startup Script" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Working Directory: $ScriptDir" -ForegroundColor Green

# Display script parameters info
if ($Clean) { Write-Host "Clean mode: Will recreate virtual environment" -ForegroundColor Magenta }
if ($Dev) { Write-Host "Development mode: Hot reload enabled" -ForegroundColor Magenta }
if ($ForceInstall) { Write-Host "Force install: Will reinstall all dependencies" -ForegroundColor Magenta }

# Clean virtual environment if needed
if ($Clean) {
    $venvPath = Join-Path $ScriptDir "venv"
    if (Test-Path $venvPath) {
        Write-Host "`nCleaning existing virtual environment..." -ForegroundColor Yellow
        Remove-Item $venvPath -Recurse -Force
        Write-Host "Virtual environment cleaned" -ForegroundColor Green
    }
}

# Use environment setup script to prepare environment
Write-Host "`nSetting up Python environment..." -ForegroundColor Yellow
try {
    $setupScript = Join-Path $ScriptDir "setup_environment.ps1"
    if (-not (Test-Path $setupScript)) {
        throw "Environment setup script not found: $setupScript"
    }
    
    # Import environment setup script
    . $setupScript
    
    # Setup parameters
    $setupArgs = @{}
    if ($ForceInstall) { $setupArgs["ForceInstall"] = $true }
    $setupArgs["Quiet"] = $false
    
    # Execute environment initialization
    $result = Initialize-Environment @setupArgs
    
    if (-not $result) {
        throw "Environment setup failed"
    }
    
} catch {
    Write-Host "Environment setup failed: $_" -ForegroundColor Red
    Read-Host "Press any key to exit"
    exit 1
}

# Start server
Write-Host "`nStarting server..." -ForegroundColor Yellow
Write-Host "Server address: http://$ServerHost`:$Port" -ForegroundColor Cyan
Write-Host "API documentation: http://$ServerHost`:$Port/docs" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop server" -ForegroundColor Yellow
Write-Host "=====================================" -ForegroundColor Cyan

try {
    if ($Dev) {
        # Development mode with hot reload
        Write-Host "Starting in development mode (hot reload enabled)..." -ForegroundColor Magenta
        uvicorn llm_server:app --host $ServerHost --port $Port --reload
    } else {
        # Production mode
        uvicorn llm_server:app --host $ServerHost --port $Port
    }
} catch {
    Write-Host "`nServer startup failed: $_" -ForegroundColor Red
    Write-Host "Please check if port $Port is already in use" -ForegroundColor Yellow
    Read-Host "Press any key to exit"
    exit 1
}

Write-Host "`nServer stopped" -ForegroundColor Yellow