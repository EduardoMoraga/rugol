@echo off
:: ===========================================================================
:: Rogologo installer — Windows entrypoint
:: Delegates to PowerShell so we get colors, prompts, and proper error handling.
:: ===========================================================================
setlocal

set "ROOT=%~dp0.."
pushd "%ROOT%"

echo.
echo ==========================================
echo   Rogologo - Agent Operations Center
echo   Setup wizard
echo ==========================================
echo.

where powershell >nul 2>&1
if errorlevel 1 (
    echo ERROR: PowerShell is required but was not found in PATH.
    echo Install Windows PowerShell or PowerShell 7 and try again.
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0wizard.ps1" %*
set RC=%errorlevel%

popd
exit /b %RC%
