# ====================================
# ITrack FastAPI Environment Setup Script
# ====================================
# 
# This script handles Python environment and dependency setup
# Can be called by other scripts for consistent environment preparation
#
# Features:
#   - Check Python and pip
#   - Create/activate virtual environment
#   - Smart dependency checking and installation
#   - Verify required files
#   - Create configuration files
# ====================================

param(
    [switch]$ForceInstall,                        # Force reinstall dependencies
    [switch]$SkipVenvCreation,                    # Skip virtual environment creation (assume exists)
    [switch]$Quiet                               # Minimal output
)

# Set error handling
$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = $PSScriptRoot

function Write-SetupHost {
    param($Message, $Color = "White")
    if (-not $Quiet) {
        Write-Host $Message -ForegroundColor $Color
    }
}

function Test-Dependencies {
    param($RequirementsFile)
    
    try {
        # Use pip check to verify all dependencies are satisfied
        $pipCheckResult = pip check 2>$null
        if ($LASTEXITCODE -eq 0) {
            # Additional check: verify specific packages from requirements.txt exist
            $requirements = Get-Content $RequirementsFile | Where-Object { $_ -notmatch "^#" -and $_.Trim() -ne "" }
            $missingPackages = @()
            
            foreach ($requirement in $requirements) {
                # Extract package name (before any version specifiers and extras like [standard])
                $packageName = ($requirement -split "[>=<!=\[]")[0].Trim()
                if ($packageName) {
                    try {
                        # Reset LASTEXITCODE before checking
                        $LASTEXITCODE = 0
                        $showResult = pip show $packageName 2>$null
                        if ($LASTEXITCODE -ne 0) {
                            $missingPackages += $packageName
                        }
                    } catch {
                        $missingPackages += $packageName
                    }
                }
            }
            
            if ($missingPackages.Count -eq 0) {
                return $true
            } else {
                if (-not $Quiet) {
                    Write-SetupHost "Missing packages: $($missingPackages -join ', ')" -Color "Yellow"
                }
                return $false
            }
        } else {
            if (-not $Quiet) {
                Write-SetupHost "Dependency conflicts detected: $pipCheckResult" -Color "Yellow"
            }
            return $false
        }
    } catch {
        if (-not $Quiet) {
            Write-SetupHost "Unable to check dependencies: $_" -Color "Yellow"
        }
        return $false
    }
}

# Main setup function
function Initialize-Environment {
    Write-SetupHost "Setting up Python environment..." -Color "Yellow"
    
    # Check if Python is installed
    Write-SetupHost "Checking Python environment..." -Color "Yellow"
    try {
        $pythonVersion = python --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Python not found"
        }
        Write-SetupHost "Python installed: $pythonVersion" -Color "Green"
        
        # Check if Python version meets requirements (3.1+)
        $versionNumber = ($pythonVersion -split " ")[1]
        $majorVersion = [int]($versionNumber -split "\.")[0]
        $minorVersion = [int]($versionNumber -split "\.")[1]
        
        if ($majorVersion -lt 3 -or ($majorVersion -eq 3 -and $minorVersion -lt 1)) {
            throw "Python version too low, requires Python 3.1 or higher"
        }
    } catch {
        Write-SetupHost "Error: $_" -Color "Red"
        throw "Python environment check failed"
    }

    # Check if pip is available
    Write-SetupHost "Checking pip..." -Color "Yellow"
    try {
        $pipVersion = pip --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "pip not found"
        }
        Write-SetupHost "pip installed: $pipVersion" -Color "Green"
    } catch {
        Write-SetupHost "Error: $_" -Color "Red"
        throw "pip check failed"
    }

    # Virtual environment management
    if (-not $SkipVenvCreation) {
        $venvPath = Join-Path $ScriptDir "venv"
        $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"

        # Create virtual environment if it doesn't exist
        if (-not (Test-Path $venvPath)) {
            Write-SetupHost "Creating virtual environment..." -Color "Yellow"
            try {
                python -m venv venv
                Write-SetupHost "Virtual environment created successfully" -Color "Green"
            } catch {
                Write-SetupHost "Failed to create virtual environment: $_" -Color "Red"
                throw "Virtual environment creation failed"
            }
        } else {
            Write-SetupHost "Virtual environment already exists" -Color "Green"
        }

        # Activate virtual environment
        Write-SetupHost "Activating virtual environment..." -Color "Yellow"
        try {
            if (Test-Path $activateScript) {
                & $activateScript
                Write-SetupHost "Virtual environment activated" -Color "Green"
            } else {
                throw "Activation script not found: $activateScript"
            }
        } catch {
            Write-SetupHost "Failed to activate virtual environment: $_" -Color "Red"
            throw "Virtual environment activation failed"
        }
    }

    # Upgrade pip
    Write-SetupHost "Upgrading pip..." -Color "Yellow"
    try {
        python -m pip install --upgrade pip 2>$null
        Write-SetupHost "pip upgrade completed" -Color "Green"
    } catch {
        Write-SetupHost "Warning: pip upgrade failed, continuing with current version" -Color "Yellow"
    }

    # Check and install dependencies
    Write-SetupHost "Checking dependencies..." -Color "Yellow"
    $requirementsFile = Join-Path $ScriptDir "requirements.txt"

    if (-not (Test-Path $requirementsFile)) {
        Write-SetupHost "requirements.txt file not found" -Color "Red"
        throw "requirements.txt not found"
    }

    # Check if dependencies are already satisfied
    $dependenciesSatisfied = Test-Dependencies -RequirementsFile $requirementsFile

    if ($ForceInstall) {
        Write-SetupHost "Force reinstalling dependencies..." -Color "Yellow"
        $dependenciesSatisfied = $false
    }

    if ($dependenciesSatisfied) {
        Write-SetupHost "All dependencies are already satisfied" -Color "Green"
    } else {
        Write-SetupHost "Installing missing dependencies..." -Color "Yellow"
        try {
            if (-not $Quiet) {
                Write-SetupHost "Installing dependencies, this may take several minutes..." -Color "Yellow"
                pip install -r requirements.txt
            } else {
                pip install -r requirements.txt 2>$null
            }
            Write-SetupHost "Dependencies installation completed" -Color "Green"
            
            # Verify installation
            Write-SetupHost "Verifying installation..." -Color "Yellow"
            Start-Sleep -Seconds 2  # Give pip time to finalize installation
            $verificationResult = Test-Dependencies -RequirementsFile $requirementsFile
            if (-not $verificationResult) {
                Write-SetupHost "Warning: Some dependencies may not be properly installed" -Color "Yellow"
            } else {
                Write-SetupHost "All dependencies verified successfully" -Color "Green"
            }
        } catch {
            Write-SetupHost "Dependencies installation failed: $_" -Color "Red"
            throw "Dependencies installation failed"
        }
    }

    # Check required files
    Write-SetupHost "Checking required files..." -Color "Yellow"
    $requiredFiles = @(
        "llm_server.py",
        "vector_utils.py",
        "refine_desc_prompt_template.md",
        "final_rca_template.md"
    )

    $missingFiles = @()
    foreach ($file in $requiredFiles) {
        $filePath = Join-Path $ScriptDir $file
        if (-not (Test-Path $filePath)) {
            $missingFiles += $file
        } else {
            Write-SetupHost "Found: $file" -Color "Green"
        }
    }

    if ($missingFiles.Count -gt 0) {
        Write-SetupHost "Missing required files:" -Color "Red"
        foreach ($file in $missingFiles) {
            Write-SetupHost "   - $file" -Color "Red"
        }
        throw "Required files missing"
    }

    # Check .env file
    $envFile = Join-Path $ScriptDir ".env"
    if (-not (Test-Path $envFile)) {
        Write-SetupHost "Warning: .env file not found" -Color "Yellow"
        Write-SetupHost "Creating sample .env file..." -Color "Yellow"
        
        $envContent = @"
# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# Other configuration options
# LOG_LEVEL=INFO
# MAX_CONCURRENT_REQUESTS=10
"@
        
        try {
            $envContent | Out-File -FilePath $envFile -Encoding UTF8
            Write-SetupHost "Sample .env file created" -Color "Green"
            Write-SetupHost "Please edit .env file and add your OpenAI API Key" -Color "Yellow"
        } catch {
            Write-SetupHost "Failed to create .env file: $_" -Color "Red"
        }
    } else {
        Write-SetupHost ".env file exists" -Color "Green"
    }

    # Create logs directory
    $logsDir = Join-Path $ScriptDir "logs"
    if (-not (Test-Path $logsDir)) {
        try {
            New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
            Write-SetupHost "Logs directory created" -Color "Green"
        } catch {
            Write-SetupHost "Warning: Failed to create logs directory" -Color "Yellow"
        }
    }

    Write-SetupHost "Environment setup completed successfully" -Color "Green"
    return $true
}

# If called directly, run the initialization
if ($MyInvocation.InvocationName -ne ".") {
    try {
        Initialize-Environment
    } catch {
        Write-SetupHost "Environment setup failed: $_" -Color "Red"
        exit 1
    }
} 