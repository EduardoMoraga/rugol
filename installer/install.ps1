# rugol installer (Windows) — native, no Docker.
#   iwr -useb https://raw.githubusercontent.com/EduardoMoraga/rugol/main/installer/install.ps1 | iex
#
# Provisions its OWN runtimes (Python via uv, Node pinned) — nothing preinstalled needed.
# Env overrides: RUGOL_HOME, RUGOL_SRC (install from a local dir), RUGOL_REPO, RUGOL_REF
$ErrorActionPreference = "Stop"

$HomeDir = if ($env:RUGOL_HOME) { $env:RUGOL_HOME } else { Join-Path $HOME ".rugol" }
$AppDir  = Join-Path $HomeDir "app"
$RT      = Join-Path $HomeDir "runtime"
$BinDir  = Join-Path $HomeDir "bin"
$Repo    = if ($env:RUGOL_REPO) { $env:RUGOL_REPO } else { "https://github.com/EduardoMoraga/rugol.git" }
$Ref     = if ($env:RUGOL_REF) { $env:RUGOL_REF } else { "main" }
$NodeVer = "v20.18.1"

function Ok($m)   { Write-Host "  [OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [!] $m"  -ForegroundColor Yellow }
function Die($m)  { Write-Host "  [X] $m"  -ForegroundColor Red; exit 1 }
function Have($c) { return [bool](Get-Command $c -ErrorAction SilentlyContinue) }

Write-Host ""
Write-Host "Instalando rugol -> $HomeDir  (sin Docker)" -ForegroundColor White
Write-Host ""

# ── 1) Código ────────────────────────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path $HomeDir | Out-Null
if ($env:RUGOL_SRC) {
    if (-not (Test-Path $env:RUGOL_SRC)) { Die "RUGOL_SRC no existe: $($env:RUGOL_SRC)" }
    if (Test-Path $AppDir) { Remove-Item -Recurse -Force $AppDir }
    New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
    robocopy $env:RUGOL_SRC $AppDir /E /XD .git node_modules .next .venv data logs /NFL /NDL /NJH /NJS /NC /NS | Out-Null
    Ok "código copiado"
} else {
    if (-not (Have "git")) { Die "git no está instalado." }
    if (Test-Path (Join-Path $AppDir ".git")) { git -C $AppDir pull --ff-only; Ok "código actualizado" }
    else { if (Test-Path $AppDir) { Remove-Item -Recurse -Force $AppDir }; git clone --depth 1 --branch $Ref $Repo $AppDir; Ok "código clonado ($Ref)" }
}
foreach ($d in @("data", "logs", "agents", "skills", "run")) { New-Item -ItemType Directory -Force -Path (Join-Path $HomeDir $d) | Out-Null }
New-Item -ItemType Directory -Force -Path $RT | Out-Null

# ── 2) Python aislado vía uv ─────────────────────────────────────────────────
if (-not (Have "uv")) {
    Write-Host "  instalando uv (gestor de Python)..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:PATH = "$HOME\.local\bin;$env:PATH"
}
if (-not (Have "uv")) { Die "uv no quedó disponible" }
Ok "uv: $(uv --version)"
Write-Host "  creando entorno Python aislado + dependencias del backend..."
uv venv "$RT\venv" --python 3.12 --clear | Out-Null
uv pip install --python "$RT\venv\Scripts\python.exe" -q -r "$AppDir\core\requirements.txt"
Ok "backend listo"

# ── 3) Node (sistema si >=18, si no lo bajamos) ──────────────────────────────
$needNode = $true
if (Have "node") {
    $maj = (node -p 'process.versions.node.split(".")[0]')
    if ([int]$maj -ge 18) { $needNode = $false; Ok "node del sistema: $(node --version)" }
}
if ($needNode) {
    $arch = if ([Environment]::Is64BitOperatingSystem) { "x64" } else { "x86" }
    $url = "https://nodejs.org/dist/$NodeVer/node-$NodeVer-win-$arch.zip"
    Write-Host "  bajando Node $NodeVer (win-$arch)..."
    $zip = Join-Path $env:TEMP "rugol-node.zip"
    Invoke-WebRequest $url -OutFile $zip
    $tmp = Join-Path $env:TEMP "rugol-node-extract"
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    Expand-Archive $zip -DestinationPath $tmp -Force
    $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
    if (Test-Path "$RT\node") { Remove-Item -Recurse -Force "$RT\node" }
    Move-Item $inner.FullName "$RT\node"
    $env:PATH = "$RT\node;$env:PATH"
    corepack enable pnpm 2>$null
    Ok "node embebido en $RT\node"
}

# ── 4) Launcher ──────────────────────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
Copy-Item (Join-Path $AppDir "cli\rugol.ps1") $BinDir -Force
Copy-Item (Join-Path $AppDir "cli\rugol.cmd") $BinDir -Force
Ok "launcher instalado en $BinDir"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$BinDir", "User")
    Warn "Agregué $BinDir al PATH. Abrí una terminal nueva para que tome efecto."
}

# ── 5) Compilar dashboard ────────────────────────────────────────────────────
Write-Host "  compilando el dashboard..."
& "$BinDir\rugol.cmd" build | Out-Null
if (Test-Path (Join-Path $AppDir "dashboard\.next\standalone\server.js")) { Ok "dashboard compilado" } else { Warn "el dashboard no compiló — corré 'rugol build'" }

Write-Host ""
Write-Host "Listo - sin Docker. Próximos pasos:" -ForegroundColor Green
Write-Host ""
Write-Host "   rugol setup    # auth + modelo + Telegram"
Write-Host "   rugol up       # levanta todo y abre el dashboard"
Write-Host ""
