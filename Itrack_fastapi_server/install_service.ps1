# ====================================
# ITrack FastAPI Server Windows Service Installer
# ====================================
#
# Usage Examples:
#   .\install_service.ps1                        # Install service with default settings
#   .\install_service.ps1 -ServiceName "MyAPI"   # Install with custom service name
#   .\install_service.ps1 -Port 9000             # Install with custom port
#   .\install_service.ps1 -DownloadNSSM          # Force download NSSM to current directory
#   .\install_service.ps1 -Uninstall             # Uninstall the service
#   .\install_service.ps1 -Status                # Check service status
#
# Note: This script must be run as Administrator
# ====================================

param(
    [string]$ServiceName = "ITrackFastAPI",        # Windows service name
    [int]$Port = 8000,                            # Server port
    [string]$ServerHost = "0.0.0.0",              # Server host
    [switch]$Uninstall,                           # Uninstall service
    [switch]$Status,                              # Check service status
    [switch]$ForceInstall,                        # Force reinstall dependencies
    [string]$NSSMPath = "",                       # Custom NSSM path (optional)
    [switch]$DownloadNSSM                         # Force download NSSM to current directory
)

# Set error handling
$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = $PSScriptRoot
Set-Location $ScriptDir

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "ITrack FastAPI Windows Service Manager" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Working Directory: $ScriptDir" -ForegroundColor Green

# Check if running as administrator
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
    Write-Host "Error: This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Please right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    Read-Host "Press any key to exit"
    exit 1
}

# Check service status
if ($Status) {
    Write-Host "`nChecking service status..." -ForegroundColor Yellow
    try {
        $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($service) {
            Write-Host "Service '$ServiceName' exists" -ForegroundColor Green
            Write-Host "Status: $($service.Status)" -ForegroundColor Cyan
            Write-Host "Start Type: $($service.StartType)" -ForegroundColor Cyan
        } else {
            Write-Host "Service '$ServiceName' not found" -ForegroundColor Red
        }
    } catch {
        Write-Host "Error checking service: $_" -ForegroundColor Red
    }
    Read-Host "Press any key to exit"
    exit 0
}

# Uninstall service
if ($Uninstall) {
    Write-Host "`nUninstalling service '$ServiceName'..." -ForegroundColor Yellow
    
    try {
        # Stop service if running
        $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($service -and $service.Status -eq "Running") {
            Write-Host "Stopping service..." -ForegroundColor Yellow
            Stop-Service -Name $ServiceName -Force
            Write-Host "Service stopped" -ForegroundColor Green
        }
        
        # Remove service using NSSM
        if ($NSSMPath) {
            $nssmExe = $NSSMPath
        } else {
            $nssmExe = "nssm"
        }
        
        & $nssmExe remove $ServiceName confirm
        Write-Host "Service '$ServiceName' removed successfully" -ForegroundColor Green
        
    } catch {
        Write-Host "Error removing service: $_" -ForegroundColor Red
        Write-Host "You may need to remove the service manually using: sc delete $ServiceName" -ForegroundColor Yellow
    }
    
    Read-Host "Press any key to exit"
    exit 0
}

# Install service
Write-Host "`nInstalling Windows Service..." -ForegroundColor Yellow

# Function to download and setup NSSM
function Install-NSSM {
    param($InstallDir)
    
    Write-Host "Downloading NSSM..." -ForegroundColor Yellow
    $nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
    $tempZip = Join-Path $env:TEMP "nssm.zip"
    $tempExtract = Join-Path $env:TEMP "nssm_temp"
    
    try {
        # Download NSSM
        Invoke-WebRequest -Uri $nssmUrl -OutFile $tempZip -UseBasicParsing
        
        # Extract
        Expand-Archive -Path $tempZip -DestinationPath $tempExtract -Force
        
        # Determine architecture
        $arch = if ([Environment]::Is64BitOperatingSystem) { "win64" } else { "win32" }
        $nssmSource = Join-Path $tempExtract "nssm-2.24\$arch\nssm.exe"
        $nssmDest = Join-Path $InstallDir "nssm.exe"
        
        # Copy NSSM to install directory
        if (-not (Test-Path $InstallDir)) {
            New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
        }
        Copy-Item -Path $nssmSource -Destination $nssmDest -Force
        
        # Clean up temp files
        Remove-Item $tempZip -Force -ErrorAction SilentlyContinue
        Remove-Item $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
        
        Write-Host "NSSM downloaded and installed to: $nssmDest" -ForegroundColor Green
        return $nssmDest
        
    } catch {
        Write-Host "Failed to download NSSM: $_" -ForegroundColor Red
        throw "NSSM installation failed"
    }
}

# Check if NSSM is available
Write-Host "`nChecking NSSM..." -ForegroundColor Yellow
$nssmExe = $null

if ($DownloadNSSM) {
    # Force download NSSM
    Write-Host "Force downloading NSSM to current directory..." -ForegroundColor Yellow
    try {
        $nssmExe = Install-NSSM -InstallDir $ScriptDir
    } catch {
        Write-Host "Failed to download NSSM" -ForegroundColor Red
        Read-Host "Press any key to exit"
        exit 1
    }
} elseif ($NSSMPath) {
    # Use specified NSSM path
    if (Test-Path $NSSMPath) {
        $nssmExe = $NSSMPath
        Write-Host "Using specified NSSM: $NSSMPath" -ForegroundColor Green
    } else {
        Write-Host "NSSM not found at specified path: $NSSMPath" -ForegroundColor Red
        Read-Host "Press any key to exit"
        exit 1
    }
} else {
    # Check if NSSM is in PATH
    try {
        $nssmCheck = Get-Command nssm -ErrorAction Stop
        $nssmExe = "nssm"
        Write-Host "NSSM found in PATH: $($nssmCheck.Source)" -ForegroundColor Green
    } catch {
        # Check if NSSM exists in current directory
        $localNSSM = Join-Path $ScriptDir "nssm.exe"
        if (Test-Path $localNSSM) {
            $nssmExe = $localNSSM
            Write-Host "Using local NSSM: $localNSSM" -ForegroundColor Green
        } else {
            # NSSM not found, offer to download
            Write-Host "NSSM not found in PATH or current directory" -ForegroundColor Yellow
            $choice = Read-Host "Would you like to download NSSM automatically to current directory? (Y/n)"
            
            if ($choice -eq "" -or $choice -eq "y" -or $choice -eq "Y") {
                try {
                    $nssmExe = Install-NSSM -InstallDir $ScriptDir
                } catch {
                    Write-Host "Automatic NSSM installation failed" -ForegroundColor Red
                    Write-Host "Please manually download NSSM from: https://nssm.cc/download" -ForegroundColor Yellow
                    Write-Host "Extract and place nssm.exe in the current directory or add to PATH" -ForegroundColor Yellow
                    Read-Host "Press any key to exit"
                    exit 1
                }
            } else {
                Write-Host "Please download NSSM from: https://nssm.cc/download" -ForegroundColor Yellow
                Write-Host "Options:" -ForegroundColor Yellow
                Write-Host "1. Extract and place nssm.exe in current directory: $ScriptDir" -ForegroundColor Yellow
                Write-Host "2. Add NSSM to system PATH" -ForegroundColor Yellow
                Write-Host "3. Use -NSSMPath parameter to specify location" -ForegroundColor Yellow
                Read-Host "Press any key to exit"
                exit 1
            }
        }
    }
}

# Run environment setup to ensure everything is ready
Write-Host "`nSetting up Python environment and dependencies..." -ForegroundColor Yellow
try {
    $setupScript = Join-Path $ScriptDir "setup_environment.ps1"
    if (-not (Test-Path $setupScript)) {
        throw "Environment setup script not found: $setupScript"
    }
    
    # Import the setup script and run initialization
    . $setupScript
    
    $setupArgs = @{}
    if ($ForceInstall) { $setupArgs["ForceInstall"] = $true }
    $setupArgs["Quiet"] = $false
    
    Write-Host "Running environment setup (this may take a few minutes)..." -ForegroundColor Yellow
    $result = Initialize-Environment @setupArgs
    
    if ($result) {
        Write-Host "Environment setup completed" -ForegroundColor Green
    } else {
        throw "Environment setup returned false"
    }
    
} catch {
    Write-Host "Environment setup failed: $_" -ForegroundColor Red
    Read-Host "Press any key to exit"
    exit 1
}

# Get Python executable path in virtual environment
$venvPath = Join-Path $ScriptDir "venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"
$uvicornScript = Join-Path $venvPath "Scripts\uvicorn.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "Python executable not found: $pythonExe" -ForegroundColor Red
    Read-Host "Press any key to exit"
    exit 1
}

if (-not (Test-Path $uvicornScript)) {
    Write-Host "Uvicorn executable not found: $uvicornScript" -ForegroundColor Red
    Read-Host "Press any key to exit"
    exit 1
}

# Check if service already exists
$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "Warning: Service '$ServiceName' already exists" -ForegroundColor Yellow
    $choice = Read-Host "Do you want to remove and reinstall it? (y/N)"
    if ($choice -eq "y" -or $choice -eq "Y") {
        Write-Host "Removing existing service..." -ForegroundColor Yellow
        if ($existingService.Status -eq "Running") {
            Stop-Service -Name $ServiceName -Force
        }
        & $nssmExe remove $ServiceName confirm
        Write-Host "Existing service removed" -ForegroundColor Green
    } else {
        Write-Host "Installation cancelled" -ForegroundColor Yellow
        Read-Host "Press any key to exit"
        exit 0
    }
}

# Install service with NSSM
Write-Host "`nInstalling service '$ServiceName'..." -ForegroundColor Yellow
try {
    # Create the service
    & $nssmExe install $ServiceName $uvicornScript "llm_server:app" "--host" $ServerHost "--port" $Port
    
    # Set service parameters
    & $nssmExe set $ServiceName AppDirectory $ScriptDir
    & $nssmExe set $ServiceName DisplayName "ITrack FastAPI Server"
    & $nssmExe set $ServiceName Description "ITrack FastAPI Server with AI-powered incident analysis"
    & $nssmExe set $ServiceName Start SERVICE_AUTO_START
    
    # Set logging
    $logsDir = Join-Path $ScriptDir "logs"
    if (-not (Test-Path $logsDir)) {
        New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    }
    
    $stdoutLog = Join-Path $logsDir "service_stdout.log"
    $stderrLog = Join-Path $logsDir "service_stderr.log"
    
    & $nssmExe set $ServiceName AppStdout $stdoutLog
    & $nssmExe set $ServiceName AppStderr $stderrLog
    & $nssmExe set $ServiceName AppRotateFiles 1
    & $nssmExe set $ServiceName AppRotateOnline 1
    & $nssmExe set $ServiceName AppRotateSeconds 86400  # Daily rotation
    & $nssmExe set $ServiceName AppRotateBytes 10485760  # 10MB max
    
    # Set restart behavior
    & $nssmExe set $ServiceName AppRestartDelay 5000  # 5 seconds
    & $nssmExe set $ServiceName AppExit Default Restart
    & $nssmExe set $ServiceName AppStopMethodSkip 6  # Skip WM_CLOSE, WM_QUIT etc
    & $nssmExe set $ServiceName AppKillProcessTree 1  # Kill child processes
    
    Write-Host "Service installed successfully" -ForegroundColor Green
    
    # Start the service
    Write-Host "`nStarting service..." -ForegroundColor Yellow
    Start-Service -Name $ServiceName
    
    # Wait a moment and check status
    Start-Sleep -Seconds 3
    $service = Get-Service -Name $ServiceName
    
    if ($service.Status -eq "Running") {
        Write-Host "Service started successfully" -ForegroundColor Green
        Write-Host "`nService Information:" -ForegroundColor Cyan
        Write-Host "Name: $ServiceName" -ForegroundColor White
        Write-Host "Status: $($service.Status)" -ForegroundColor Green
        Write-Host "Server URL: http://$ServerHost`:$Port" -ForegroundColor Cyan
        Write-Host "API Docs: http://$ServerHost`:$Port/docs" -ForegroundColor Cyan
        Write-Host "Logs Directory: $logsDir" -ForegroundColor Yellow
        
        Write-Host "`nService Management Commands:" -ForegroundColor Magenta
        Write-Host "Start:   Start-Service -Name '$ServiceName'" -ForegroundColor White
        Write-Host "Stop:    Stop-Service -Name '$ServiceName'" -ForegroundColor White
        Write-Host "Restart: Restart-Service -Name '$ServiceName'" -ForegroundColor White
        Write-Host "Status:  Get-Service -Name '$ServiceName'" -ForegroundColor White
        Write-Host "Remove:  .\install_service.ps1 -Uninstall" -ForegroundColor White
        
    } else {
        Write-Host "Warning: Service installed but failed to start" -ForegroundColor Yellow
        Write-Host "Status: $($service.Status)" -ForegroundColor Red
        Write-Host "Check logs in: $logsDir" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "Service installation failed: $_" -ForegroundColor Red
    Write-Host "Please check if you have administrator privileges" -ForegroundColor Yellow
}

Write-Host "`n=====================================" -ForegroundColor Cyan
Read-Host "Press any key to exit" 