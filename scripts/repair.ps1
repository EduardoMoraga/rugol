# Rugol — reparacion de una linea (Windows).
#   irm https://raw.githubusercontent.com/EduardoMoraga/rugol/main/scripts/repair.ps1 | iex
#
# Para que existe: hasta junio de 2026 el launcher usaba `git pull`, que aborta
# si el runtime dejo archivos modificados en el directorio de la app. El fetch
# fallaba, el launcher solo se refresca DESPUES de un fetch exitoso, y por eso
# no podia arreglarse a si mismo: cada `rugol update` imprimia "codigo
# actualizado" sin bajar nada. Este script rompe ese circulo una vez.
#
# Es idempotente y no destructivo: los cambios locales van a un `git stash`
# (recuperables con `git stash pop`), y tus datos en ~/.rugol/data, agents/,
# skills/ y .env no se tocan nunca.
$ErrorActionPreference = "Continue"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$HomeDir = if ($env:RUGOL_HOME) { $env:RUGOL_HOME } else { Join-Path $HOME ".rugol" }
$AppDir  = Join-Path $HomeDir "app"
$BinDir  = Join-Path $HomeDir "bin"
$Venv    = Join-Path $HomeDir "runtime\venv\Scripts\python.exe"
$Repo    = "https://github.com/EduardoMoraga/rugol.git"
$Rugol   = Join-Path $BinDir "rugol.cmd"

function Ok($m)   { Write-Host "  [OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [!]  $m" -ForegroundColor Yellow }
function Err($m)  { Write-Host "  [X]  $m" -ForegroundColor Red }
function Step($m) { Write-Host ""; Write-Host $m -ForegroundColor White }
function Have($c) { return [bool](Get-Command $c -ErrorAction SilentlyContinue) }

$failed = $false

Write-Host ""
Write-Host "Rugol - reparacion" -ForegroundColor Cyan
Write-Host "Home: $HomeDir" -ForegroundColor DarkGray

# ── 1. Requisitos minimos ────────────────────────────────────────────────────
Step "1) Requisitos"
if (-not (Have "git")) {
    Err "git no esta instalado. Instalalo desde https://git-scm.com/download/win y volve a correr esto."
    $failed = $true
}
if (-not (Test-Path $AppDir)) {
    Err "No encuentro $AppDir. Corre el instalador completo:"
    Write-Host "     iwr -useb https://raw.githubusercontent.com/EduardoMoraga/rugol/main/installer/install.ps1 | iex"
    $failed = $true
}
if (-not $failed) { Ok "git presente, app en $AppDir" }

# ── 2. Bajar el codigo de verdad ─────────────────────────────────────────────
if (-not $failed) {
    Step "2) Codigo"
    $before = (git -C $AppDir rev-parse --short HEAD 2>$null)

    if (-not (Test-Path (Join-Path $AppDir ".git"))) {
        # Instalacion por copia (RUGOL_SRC): la convertimos en un clon sin
        # tocar los archivos no versionados que haya al lado.
        Warn "el app dir no era un repo git - lo conecto al remoto"
        git -C $AppDir init -q 2>&1 | Out-Null
        git -C $AppDir remote add origin $Repo 2>&1 | Out-Null
    }
    git -C $AppDir remote set-url origin $Repo 2>&1 | Out-Null

    # Los cambios locales van a un stash: se guardan, no se pierden.
    $dirty = (git -C $AppDir status --porcelain --untracked-files=no 2>$null)
    if ($dirty) {
        $stamp = Get-Date -Format "yyyyMMdd-HHmm"
        git -C $AppDir stash push -m "rugol repair $stamp" 2>&1 | Out-Null
        Ok "cambios locales guardados en un stash (git -C `"$AppDir`" stash list)"
    }

    git -C $AppDir fetch origin main 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Err "no pude alcanzar GitHub. Revisa la conexion y volve a correr esto."
        $failed = $true
    } else {
        git -C $AppDir reset --hard origin/main 2>&1 | Out-Null
        $after = (git -C $AppDir rev-parse --short HEAD 2>$null)
        if ($before -eq $after) { Ok "ya estabas al dia ($after)" }
        else { Ok "actualizado: $before -> $after" }
        git -C $AppDir log --oneline -1
    }
}

# ── 3. Refrescar el launcher (esto es lo que rompe el circulo) ───────────────
if (-not $failed) {
    Step "3) Launcher"
    New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
    Copy-Item (Join-Path $AppDir "cli\rugol.ps1") $BinDir -Force
    Copy-Item (Join-Path $AppDir "cli\rugol.cmd") $BinDir -Force
    Ok "rugol.ps1 y rugol.cmd actualizados en $BinDir"

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$BinDir*") {
        [Environment]::SetEnvironmentVariable("Path", "$userPath;$BinDir", "User")
        Ok "$BinDir agregado al PATH del usuario"
    }
    if (";$env:PATH;" -notlike "*;$BinDir;*") { $env:PATH = "$env:PATH;$BinDir" }
}

# ── 4. Dependencias del backend ──────────────────────────────────────────────
if (-not $failed) {
    Step "4) Backend"
    if (-not (Have "uv")) {
        Write-Host "  instalando uv (gestor de Python)..."
        try { Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression } catch { }
        $env:PATH = "$HOME\.local\bin;$env:PATH"
    }
    if (Have "uv") {
        if (-not (Test-Path $Venv)) {
            Write-Host "  creando el entorno Python aislado..."
            uv venv (Join-Path $HomeDir "runtime\venv") --python 3.12 2>&1 | Out-Null
        }
        uv pip install --python $Venv -q -r (Join-Path $AppDir "core\requirements.txt") 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { Ok "dependencias al dia" }
        else { Warn "las dependencias no se actualizaron - el backend sigue con las que tenia" }
    } else {
        Warn "no pude instalar uv. No es bloqueante: no hay dependencias nuevas."
    }
}

# ── 5. Compilar y levantar ───────────────────────────────────────────────────
if (-not $failed) {
    Step "5) Dashboard y servicios"
    # Down ANTES de compilar: en Windows el server de Next bloquea archivos de
    # .next y el build queda a medias (dashboard sin estilos).
    & $Rugol down
    & $Rugol build
    & $Rugol up
}

# ── 6. Estado ────────────────────────────────────────────────────────────────
if (-not $failed) {
    Step "6) Estado"
    & $Rugol status

    Write-Host ""
    Write-Host "Falta un solo paso, y necesita el navegador:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "    rugol login" -ForegroundColor White
    Write-Host ""
    Write-Host "Despues, para confirmar que el agente responde:" -ForegroundColor DarkGray
    Write-Host "    rugol doctor" -ForegroundColor DarkGray
    Write-Host ""
} else {
    Write-Host ""
    Err "La reparacion no termino. Resolve lo marcado arriba y volve a correr:"
    Write-Host "    irm https://raw.githubusercontent.com/EduardoMoraga/rugol/main/scripts/repair.ps1 | iex"
    Write-Host ""
}
