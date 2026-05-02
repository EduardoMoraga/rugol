@echo off
setlocal
set "ROOT=%~dp0.."
pushd "%ROOT%"

echo.
echo Stopping and removing Rogologo containers...
docker compose down -v

echo.
echo Containers removed. The repo and data folder remain on disk.
echo To wipe everything:  rmdir /s /q data logs
echo.

popd
endlocal
