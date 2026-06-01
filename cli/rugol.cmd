@echo off
REM Shim que invoca el CLI de PowerShell. Permite usar `rugol` en cmd.exe.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0rugol.ps1" %*
