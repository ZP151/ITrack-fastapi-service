@echo off
echo Setting execution policy for current process...
powershell -Command "Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; .\install_service.ps1"
pause
