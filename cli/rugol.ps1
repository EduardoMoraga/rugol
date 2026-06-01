# rugol — control plane for your Claude agents (Windows). Native, no Docker.
# Mirrors cli/rugol (bash): backend on a uv-managed Python, dashboard on a
# prebuilt Next.js server, both as plain processes. State lives in %USERPROFILE%\.rugol.
[CmdletBinding()]
param(
    [Parameter(Position = 0)][string]$Command = "help",
    [Parameter(Position = 1, ValueFromRemainingArguments = $true)][string[]]$Rest
)
$ErrorActionPreference = "Stop"

# ── Paths ────────────────────────────────────────────────────────────────────
$HomeDir = if ($env:RUGOL_HOME) { $env:RUGOL_HOME } else { Join-Path $HOME ".rugol" }
$AppDir  = if ($env:RUGOL_APP_DIR) { $env:RUGOL_APP_DIR } else { Join-Path $HomeDir "app" }
$EnvFile = Join-Path $HomeDir ".env"
$DataDir = Join-Path $HomeDir "data"
$LogsDir = Join-Path $HomeDir "logs"
$RunDir  = Join-Path $HomeDir "run"
$RT      = Join-Path $HomeDir "runtime"
$DashDir = Join-Path $AppDir "dashboard"

$CorePort = if ($env:CORE_PORT) { $env:CORE_PORT } else { "8000" }
$DashPort = if ($env:DASHBOARD_PORT) { $env:DASHBOARD_PORT } else { "3000" }

function Ok($m)   { Write-Host "  [OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [!] $m"  -ForegroundColor Yellow }
function Err($m)  { Write-Host "  [X] $m"  -ForegroundColor Red }
function Have($c) { return [bool](Get-Command $c -ErrorAction SilentlyContinue) }

# ── Runtime resolution ───────────────────────────────────────────────────────
function Resolve-Python {
    foreach ($c in @("$RT\venv\Scripts\python.exe", "$AppDir\.venv\Scripts\python.exe")) {
        if (Test-Path $c) { return $c }
    }
    return (Get-Command python -ErrorAction SilentlyContinue).Source
}
function Resolve-Node {
    $c = "$RT\node\node.exe"
    if (Test-Path $c) { return $c }
    return (Get-Command node -ErrorAction SilentlyContinue).Source
}
function Load-DotEnv($file) {
    if (-not (Test-Path $file)) { return }
    Get-Content $file | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            Set-Item -Path ("Env:" + $Matches[1]) -Value $Matches[2]
        }
    }
}
function Require-App {
    if (-not (Test-Path (Join-Path $AppDir "core\main.py"))) {
        Err "No encuentro la app en $AppDir. Reinstalá con el one-liner del README."; exit 1
    }
}
function Require-Env { if (-not (Test-Path $EnvFile)) { Err "Falta config. Corré primero:  rugol setup"; exit 1 } }

function Wait-Health([int]$Tries = 30) {
    Write-Host -NoNewline "  esperando al core"
    for ($i = 0; $i -lt $Tries; $i++) {
        try { Invoke-RestMethod "http://127.0.0.1:$CorePort/api/health" -TimeoutSec 2 | Out-Null; Write-Host ""; return $true }
        catch { Write-Host -NoNewline "."; Start-Sleep 1 }
    }
    Write-Host ""; return $false
}
function Pid-Running($file) {
    if (-not (Test-Path $file)) { return $false }
    $procId = Get-Content $file -ErrorAction SilentlyContinue
    if (-not $procId) { return $false }
    return [bool](Get-Process -Id $procId -ErrorAction SilentlyContinue)
}

# ── Process control ──────────────────────────────────────────────────────────
function Start-Backend {
    $py = Resolve-Python
    New-Item -ItemType Directory -Force -Path $RunDir, $LogsDir | Out-Null
    Load-DotEnv $EnvFile
    $env:AGENTS_DIR = Join-Path $HomeDir "agents"
    $env:SKILLS_DIR = Join-Path $HomeDir "skills"
    if (-not $env:DATABASE_URL) {
        $dbp = (Join-Path $DataDir "rugol.db") -replace '\\', '/'
        $env:DATABASE_URL = "sqlite+aiosqlite:///$dbp"
    }
    $p = Start-Process -FilePath $py `
        -ArgumentList @("-m", "uvicorn", "core.main:app", "--host", "127.0.0.1", "--port", "$CorePort") `
        -WorkingDirectory $AppDir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $LogsDir "core.out.log") `
        -RedirectStandardError  (Join-Path $LogsDir "core.err.log")
    $p.Id | Set-Content (Join-Path $RunDir "core.pid")
}
function Start-Dashboard {
    $node = Resolve-Node
    $server = Join-Path $DashDir ".next\standalone\server.js"
    if (-not (Test-Path $server)) { Warn "Dashboard no compilado — corré 'rugol build'."; return }
    $env:PORT = "$DashPort"; $env:HOSTNAME = "127.0.0.1"
    $p = Start-Process -FilePath $node -ArgumentList @($server) `
        -WorkingDirectory $DashDir -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $LogsDir "dashboard.out.log") `
        -RedirectStandardError  (Join-Path $LogsDir "dashboard.err.log")
    $p.Id | Set-Content (Join-Path $RunDir "dashboard.pid")
}
function Stop-One($pidfile, $name) {
    if (Test-Path $pidfile) {
        $procId = Get-Content $pidfile -ErrorAction SilentlyContinue
        try { Stop-Process -Id $procId -Force -ErrorAction Stop; Ok "$name detenido" } catch { Write-Host "  $name no estaba corriendo" }
        Remove-Item $pidfile -ErrorAction SilentlyContinue
    } else { Write-Host "  $name no estaba corriendo" }
}
function Build-Dashboard {
    Require-App
    $nodebin = "$RT\node"
    if (Test-Path $nodebin) { $env:PATH = "$nodebin;$env:PATH" }
    if (-not (Have "node")) { Err "Node no disponible (lo necesita el dashboard)."; return $false }
    if (-not (Have "pnpm")) { corepack enable pnpm 2>$null }
    Write-Host "Compilando el dashboard (1-2 min la primera vez)..."
    Push-Location $DashDir
    try {
        if (-not (Test-Path "node_modules")) { pnpm install }
        $env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:$CorePort"
        pnpm build
    } finally { Pop-Location }
    $sa = Join-Path $DashDir ".next\standalone\.next"
    New-Item -ItemType Directory -Force -Path $sa | Out-Null
    Copy-Item (Join-Path $DashDir ".next\static") (Join-Path $sa "static") -Recurse -Force
    if (Test-Path (Join-Path $DashDir "public")) { Copy-Item (Join-Path $DashDir "public") (Join-Path $DashDir ".next\standalone\public") -Recurse -Force }
    Ok "Dashboard compilado."
    return $true
}

# ── Commands ─────────────────────────────────────────────────────────────────
function Cmd-Setup {
    Require-App
    Write-Host ""
    Write-Host "rugol setup — configuración inicial" -ForegroundColor White
    Write-Host ""
    foreach ($d in @($HomeDir, $DataDir, $LogsDir, $RunDir, (Join-Path $HomeDir "agents"), (Join-Path $HomeDir "skills"))) {
        New-Item -ItemType Directory -Force -Path $d | Out-Null
    }
    $atpl = Join-Path $AppDir "agents-templates"; $stpl = Join-Path $AppDir "skills-templates"
    $agD = Join-Path $HomeDir "agents"; $skD = Join-Path $HomeDir "skills"
    if ((Test-Path $atpl) -and -not (Get-ChildItem $agD -ErrorAction SilentlyContinue)) { Copy-Item "$atpl\*" $agD -Recurse -Force; Ok "Agentes de ejemplo copiados" }
    if ((Test-Path $stpl) -and -not (Get-ChildItem $skD -ErrorAction SilentlyContinue)) { Copy-Item "$stpl\*" $skD -Recurse -Force; Ok "Skills de ejemplo copiadas" }

    Write-Host "1) Autenticación con Claude"
    Write-Host "   [1] Suscripción Pro/Max  (recomendado - usa tu plan, sin costo extra)"
    Write-Host "   [2] API key de Anthropic (pay-per-use, billing aislado)"
    $authChoice = Read-Host "   Opción [1]"; if (-not $authChoice) { $authChoice = "1" }
    $useSub = "true"; $apiKey = ""; $oauthToken = ""
    if ($authChoice -eq "2") {
        $useSub = "false"
        do {
            $sec = Read-Host "   ANTHROPIC_API_KEY (sk-ant-...)" -AsSecureString
            $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
            if ($apiKey -notlike "sk-ant-*") { Warn "Una API key empieza con 'sk-ant-'." }
        } while ($apiKey -notlike "sk-ant-*")
    } else {
        Write-Host "   Tu suscripción se usa con un token long-lived (claude setup-token), headless."
        if (Have "claude") {
            $gen = Read-Host "   ¿Generar el token ahora con 'claude setup-token'? [S/n]"
            if ($gen -in @("", "s", "S", "y", "Y")) {
                Write-Host "   Autorizá en el navegador y copiá el token que muestra."
                try { claude setup-token } catch { Warn "No pude correr setup-token; pegá un token existente." }
            }
        } else { Write-Host "   (el CLI 'claude' no está acá — generá el token donde lo tengas y pegalo)" }
        do {
            $sec = Read-Host "   Pegá tu token de suscripción" -AsSecureString
            $oauthToken = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
            if (-not $oauthToken) { Warn "No puede quedar vacío." }
        } while (-not $oauthToken)
    }

    Write-Host ""
    Write-Host "2) Modelo por defecto (Rugol enruta solo por tarea; este es el fallback)"
    Write-Host "   [1] Sonnet 4.6 (recomendado)   [2] Opus 4.8   [3] Haiku 4.5"
    $modelChoice = Read-Host "   Opción [1]"
    switch ($modelChoice) { "2" { $model = "claude-opus-4-8" } "3" { $model = "claude-haiku-4-5-20251001" } default { $model = "claude-sonnet-4-6" } }

    Write-Host ""
    Write-Host "3) Telegram (opcional — Enter para saltar)"
    $tgToken = Read-Host "   TELEGRAM_BOT_TOKEN"
    $tgUsers = ""; if ($tgToken) { $tgUsers = Read-Host "   User IDs permitidos (coma-separado)" }

    Write-Host ""
    Write-Host "4) Agente por defecto (responde al instante, sin /bind)"
    $defaultAgent = Read-Host "   Agente por defecto [assistant]"; if (-not $defaultAgent) { $defaultAgent = "assistant" }

    $secret = -join ((1..32) | ForEach-Object { '{0:x}' -f (Get-Random -Max 16) })
    $stamp  = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    @"
# Generado por ``rugol setup`` — $stamp
USE_SUBSCRIPTION=$useSub
ANTHROPIC_API_KEY=$apiKey
CLAUDE_CODE_OAUTH_TOKEN=$oauthToken
DEFAULT_MODEL=$model

TELEGRAM_BOT_TOKEN=$tgToken
TELEGRAM_ALLOWED_USERS=$tgUsers

DEFAULT_AGENT=$defaultAgent

CORE_PORT=$CorePort
DASHBOARD_PORT=$DashPort
SESSION_SECRET=$secret
"@ | Set-Content -Path $EnvFile -Encoding UTF8
    Write-Host ""; Ok "Configuración guardada en $EnvFile"; Write-Host ""; Write-Host "Siguiente:  rugol up"
}

function Cmd-Build { Build-Dashboard | Out-Null }

function Cmd-Up {
    Require-App; Require-Env
    Write-Host ""
    if (-not (Test-Path (Join-Path $DashDir ".next\standalone\server.js"))) { if (-not (Build-Dashboard)) { Err "No pude preparar el dashboard."; exit 1 } }
    if (Pid-Running (Join-Path $RunDir "core.pid")) { Ok "core ya estaba corriendo" }
    else { Write-Host "Levantando el core..."; Start-Backend; if (Wait-Health 30) { Ok "core saludable en http://127.0.0.1:$CorePort" } else { Warn "El core tardó. Mirá: rugol logs core" } }
    if (Pid-Running (Join-Path $RunDir "dashboard.pid")) { Ok "dashboard ya estaba corriendo" }
    else { Start-Dashboard; Ok "dashboard en http://127.0.0.1:$DashPort" }
    $dash = "http://127.0.0.1:$DashPort"
    if ((Get-Content $EnvFile -ErrorAction SilentlyContinue) -match '^TELEGRAM_BOT_TOKEN=.+') { Ok "Telegram conectado — escribile a tu bot." }
    Write-Host ""; Write-Host "  Abrí:  $dash" -ForegroundColor White
    Start-Process $dash
    Write-Host ""; Write-Host "Detener: rugol down  |  Estado: rugol status  |  Logs: rugol logs"
}
function Cmd-Down { Stop-One (Join-Path $RunDir "dashboard.pid") "dashboard"; Stop-One (Join-Path $RunDir "core.pid") "core" }
function Cmd-Restart { Cmd-Down; Start-Sleep 1; Cmd-Up }

function Cmd-Status {
    Write-Host ""; Write-Host "Servicios" -ForegroundColor White
    if (Pid-Running (Join-Path $RunDir "core.pid")) { Ok "core      (pid $(Get-Content (Join-Path $RunDir 'core.pid')))" } else { Warn "core      detenido" }
    if (Pid-Running (Join-Path $RunDir "dashboard.pid")) { Ok "dashboard (pid $(Get-Content (Join-Path $RunDir 'dashboard.pid')))" } else { Warn "dashboard detenido" }
    Write-Host ""; Write-Host "Salud" -ForegroundColor White
    try { Invoke-RestMethod "http://127.0.0.1:$CorePort/api/health" -TimeoutSec 2 | Out-Null; Ok "API → :$CorePort" } catch { Warn "API → no responde" }
    try { Invoke-WebRequest "http://127.0.0.1:$DashPort/" -TimeoutSec 2 -UseBasicParsing | Out-Null; Ok "UI  → :$DashPort" } catch { Warn "UI  → no responde" }
    Write-Host ""; Write-Host "Home   $HomeDir"
}
function Cmd-Logs {
    $svc = if ($Rest -and $Rest.Count -gt 0) { $Rest[0] } else { "core" }
    $f = if ($svc -in @("dashboard", "dash", "ui")) { Join-Path $LogsDir "dashboard.out.log" } else { Join-Path $LogsDir "core.err.log" }
    if (Test-Path $f) { Get-Content $f -Tail 100 -Wait } else { Warn "sin log todavía: $f" }
}
function Cmd-Doctor {
    Write-Host ""; Write-Host "rugol doctor" -ForegroundColor White
    $fail = 0; $py = Resolve-Python; $node = Resolve-Node
    if ($py) { Ok "python: $(& $py --version 2>&1)" } else { Err "no encontré Python"; $fail = 1 }
    if ($node) { Ok "node: $(& $node --version)" } else { Err "node no disponible"; $fail = 1 }
    if (Have "uv") { Ok "uv presente" } else { Warn "uv no está (el instalador lo usa)" }
    if (Have "claude") { Ok "claude CLI presente" } else { Warn "claude CLI no está en PATH (OK si usás API key)" }
    if (Test-Path (Join-Path $AppDir "core\main.py")) { Ok "app en $AppDir" } else { Err "app no encontrada"; $fail = 1 }
    if (Test-Path (Join-Path $DashDir ".next\standalone\server.js")) { Ok "dashboard compilado" } else { Warn "dashboard sin compilar — 'rugol build'" }
    if (Test-Path $EnvFile) {
        Ok "config presente"
        $envc = Get-Content $EnvFile
        if ($envc -match '^USE_SUBSCRIPTION=true') {
            if ($envc -match '^CLAUDE_CODE_OAUTH_TOKEN=.+') { Ok "auth: suscripción (token presente)" } else { Warn "auth: falta CLAUDE_CODE_OAUTH_TOKEN — re-corré 'rugol setup'"; $fail = 1 }
        } else {
            if ($envc -match '^ANTHROPIC_API_KEY=sk-ant-') { Ok "auth: API key" } else { Warn "auth: API key inválida — re-corré 'rugol setup'"; $fail = 1 }
        }
    } else { Warn "falta config — corré 'rugol setup'" }
    Write-Host ""
    if ($fail -eq 0) { Ok "Todo listo." } else { Err "Resolvé lo de arriba antes de 'rugol up'." }
}
function Cmd-Update {
    Require-App
    if (Test-Path (Join-Path $AppDir ".git")) { git -C $AppDir pull --ff-only; Ok "código actualizado" }
    $py = Resolve-Python
    if ($py) { Push-Location $AppDir; & $py -m pip install -q -r core/requirements.txt; Pop-Location; Ok "deps backend OK" }
    Build-Dashboard | Out-Null
    Cmd-Restart
    Ok "rugol actualizado. Tus datos en $HomeDir quedaron intactos."
}
function Cmd-Uninstall {
    $ans = Read-Host "Detener rugol y ¿borrar también tus DATOS en $HomeDir? [no/si]"
    Cmd-Down
    if ($ans -in @("si", "sí", "yes")) { Remove-Item -Recurse -Force $HomeDir; Ok "home borrado" } else { Write-Host "  Datos conservados en $HomeDir" }
}
function Cmd-Open { Start-Process "http://127.0.0.1:$DashPort" }
function Cmd-Version {
    $v = $null; $initf = Join-Path $AppDir "core\__init__.py"
    if (Test-Path $initf) { $m = Select-String -Path $initf -Pattern '__version__\s*=\s*"([^"]+)"' | Select-Object -First 1; if ($m) { $v = $m.Matches[0].Groups[1].Value } }
    Write-Host "rugol $($v ?? '(desconocida)')"
}
function Show-Usage {
@"

rugol — tu orquestador de agentes Claude, en un comando. Sin Docker.

Uso:  rugol <comando>

  setup        Configuración inicial (auth + modelo + Telegram)
  up           Levanta core + dashboard y abre el navegador
  down         Detiene todo
  restart      Reinicia
  status       Estado de servicios y salud
  logs [svc]   Logs en vivo (core | dashboard)
  doctor       Verifica runtime, puertos y configuración
  build        (Re)compila el dashboard
  open         Abre el dashboard
  update       Actualiza el código y reconstruye (datos intactos)
  uninstall    Quita rugol (pregunta si borrar datos)

Primera vez:  rugol setup  ->  rugol up
Home de datos: $HomeDir
"@ | Write-Host
}

switch ($Command.ToLower()) {
    "setup" { Cmd-Setup }
    { $_ -in @("up", "start") }   { Cmd-Up }
    { $_ -in @("down", "stop") }  { Cmd-Down }
    "restart" { Cmd-Restart }
    { $_ -in @("status", "ps") }  { Cmd-Status }
    "logs"    { Cmd-Logs }
    "doctor"  { Cmd-Doctor }
    "build"   { Cmd-Build }
    "open"    { Cmd-Open }
    { $_ -in @("update", "upgrade") }   { Cmd-Update }
    { $_ -in @("uninstall", "remove") } { Cmd-Uninstall }
    { $_ -in @("version", "--version", "-v") } { Cmd-Version }
    default   { Show-Usage }
}
