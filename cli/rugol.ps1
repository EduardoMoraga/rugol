# rugol - control plane for your Claude agents (Windows). Native, no Docker.
# Mirrors cli/rugol (bash): backend on a uv-managed Python, dashboard on a
# prebuilt Next.js server, both as plain processes. State lives in %USERPROFILE%\.rugol.
[CmdletBinding()]
param(
    [Parameter(Position = 0)][string]$Command = "help",
    [Parameter(Position = 1, ValueFromRemainingArguments = $true)][string[]]$Rest
)
$ErrorActionPreference = "Stop"
# UTF-8 en consola para que los acentos no salgan como "??".
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

# __ Paths ____________________________________________________________________
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

# __ Runtime resolution _______________________________________________________
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
        Err "No encuentro la app en $AppDir. Reinstala con el one-liner del README."; exit 1
    }
}
function Require-Env { if (-not (Test-Path $EnvFile)) { Err "Falta config. Corre primero:  rugol setup"; exit 1 } }

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

# __ Process control __________________________________________________________
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
    if (-not (Test-Path $server)) { Warn "Dashboard no compilado - corre 'rugol build'."; return }
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
    # Senaliza el resultado por script-scope ($script:BuildOk) en vez de
    # devolver un booleano: asi la salida de npm/pnpm fluye a la consola en
    # vez de quedar capturada por un pipe del caller (la causa de "no compilo"
    # sin ningun detalle). Los callers leen $script:BuildOk.
    $script:BuildOk = $false
    Require-App
    # Node del sistema si esta; el embebido solo como fallback (evita usar un
    # node viejo de una instalacion previa).
    if ((-not (Have "node")) -and (Test-Path "$RT\node\node.exe")) { $env:PATH = "$RT\node;$env:PATH" }
    if (-not (Have "node")) { Err "Node no disponible (lo necesita el dashboard)."; return }
    # Usamos npm (viene con Node). NO corepack/pnpm: su verificacion de firma
    # falla en varias versiones de Node ('Cannot find matching keyid'). npm
    # compila el dashboard igual (es un Next app estandar, 'next build').
    Write-Host "Compilando el dashboard con npm (1-2 min la primera vez)..."
    Push-Location $DashDir
    $built = $false
    try {
        $env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:$CorePort"
        npm install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { Err "'npm install' fallo (codigo $LASTEXITCODE)."; return }
        npm run build
        $built = ($LASTEXITCODE -eq 0)
        if (-not $built) { Err "'npm run build' fallo (codigo $LASTEXITCODE)." }
    } finally { Pop-Location }
    if (-not $built) { return }
    $sa = Join-Path $DashDir ".next\standalone\.next"
    New-Item -ItemType Directory -Force -Path $sa | Out-Null
    Copy-Item (Join-Path $DashDir ".next\static") (Join-Path $sa "static") -Recurse -Force
    if (Test-Path (Join-Path $DashDir "public")) { Copy-Item (Join-Path $DashDir "public") (Join-Path $DashDir ".next\standalone\public") -Recurse -Force }
    Ok "Dashboard compilado."
    $script:BuildOk = $true
}

# __ Commands _________________________________________________________________
function Cmd-Setup {
    Require-App
    Write-Host ""
    Write-Host "rugol setup - configuracion inicial" -ForegroundColor White
    Write-Host ""
    foreach ($d in @($HomeDir, $DataDir, $LogsDir, $RunDir, (Join-Path $HomeDir "agents"), (Join-Path $HomeDir "skills"))) {
        New-Item -ItemType Directory -Force -Path $d | Out-Null
    }
    $atpl = Join-Path $AppDir "agents-templates"; $stpl = Join-Path $AppDir "skills-templates"
    $agD = Join-Path $HomeDir "agents"; $skD = Join-Path $HomeDir "skills"
    if ((Test-Path $atpl) -and -not (Get-ChildItem $agD -ErrorAction SilentlyContinue)) { Copy-Item "$atpl\*" $agD -Recurse -Force; Ok "Agentes de ejemplo copiados" }
    if ((Test-Path $stpl) -and -not (Get-ChildItem $skD -ErrorAction SilentlyContinue)) { Copy-Item "$stpl\*" $skD -Recurse -Force; Ok "Skills de ejemplo copiadas" }

    Write-Host "1) Autenticacion con Claude"
    Write-Host "   [1] Suscripcion Pro/Max  (recomendado - usa tu plan, sin costo extra)"
    Write-Host "   [2] API key de Anthropic (pay-per-use, billing aislado)"
    $authChoice = Read-Host "   Opcion [1]"; if (-not $authChoice) { $authChoice = "1" }
    $useSub = "true"; $apiKey = ""; $oauthToken = ""
    if ($authChoice -eq "2") {
        $useSub = "false"
        do {
            $sec = Read-Host "   ANTHROPIC_API_KEY (sk-ant-...)" -AsSecureString
            $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
            if ($apiKey -notlike "sk-ant-*") { Warn "Una API key empieza con 'sk-ant-'." }
        } while ($apiKey -notlike "sk-ant-*")
    } else {
        Write-Host "   Tu suscripcion se usa con un token long-lived (claude setup-token), headless."
        if (Have "claude") {
            $gen = Read-Host "   Generar el token ahora con 'claude setup-token'? [S/n]"
            if ($gen -in @("", "s", "S", "y", "Y")) {
                Write-Host "   Autoriza en el navegador y copia el token que muestra."
                try { claude setup-token } catch { Warn "No pude correr setup-token; pega un token existente." }
            }
        } else { Write-Host "   (el CLI 'claude' no esta aca - genera el token donde lo tengas y pegalo)" }
        do {
            $sec = Read-Host "   Pega tu token de suscripcion" -AsSecureString
            $oauthToken = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
            if (-not $oauthToken) { Warn "No puede quedar vacio." }
        } while (-not $oauthToken)
    }

    Write-Host ""
    Write-Host "2) Modelo por defecto (Rugol enruta solo por tarea; este es el fallback)"
    Write-Host "   [1] Sonnet 4.6 (recomendado)   [2] Opus 4.8   [3] Haiku 4.5"
    $modelChoice = Read-Host "   Opcion [1]"
    switch ($modelChoice) { "2" { $model = "claude-opus-4-8" } "3" { $model = "claude-haiku-4-5-20251001" } default { $model = "claude-sonnet-4-6" } }

    Write-Host ""
    Write-Host "3) Telegram (opcional - Enter para saltar)"
    $tgToken = Read-Host "   TELEGRAM_BOT_TOKEN"
    $tgUsers = ""; if ($tgToken) { $tgUsers = Read-Host "   User IDs permitidos (coma-separado)" }

    Write-Host ""
    Write-Host "4) Agente por defecto (responde al instante, sin /bind)"
    $defaultAgent = Read-Host "   Agente por defecto [assistant]"; if (-not $defaultAgent) { $defaultAgent = "assistant" }

    $secret = -join ((1..32) | ForEach-Object { '{0:x}' -f (Get-Random -Max 16) })
    $stamp  = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    @"
# Generado por ``rugol setup`` - $stamp
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
    Write-Host ""; Ok "Configuracion guardada en $EnvFile"
    # Si ya estaba corriendo, reiniciamos para aplicar la nueva config al instante
    # (el .env solo se lee al arrancar).
    if ((Pid-Running (Join-Path $RunDir "core.pid")) -or (Pid-Running (Join-Path $RunDir "dashboard.pid"))) {
        Write-Host ""; Write-Host "Rugol estaba corriendo - lo reinicio para aplicar la nueva configuracion..."; Cmd-Restart
    } else { Write-Host ""; Write-Host "Siguiente:  rugol up" }
}

function Cmd-Build { Build-Dashboard }

function Cmd-Up {
    Require-App; Require-Env
    Write-Host ""
    if (-not (Test-Path (Join-Path $DashDir ".next\standalone\server.js"))) { Build-Dashboard; if (-not $script:BuildOk) { Err "No pude preparar el dashboard."; exit 1 } }
    if (Pid-Running (Join-Path $RunDir "core.pid")) { Ok "core ya estaba corriendo" }
    else { Write-Host "Levantando el core..."; Start-Backend; if (Wait-Health 30) { Ok "core saludable en http://127.0.0.1:$CorePort" } else { Warn "El core tardo. Mira: rugol logs core" } }
    if (Pid-Running (Join-Path $RunDir "dashboard.pid")) { Ok "dashboard ya estaba corriendo" }
    else { Start-Dashboard; Ok "dashboard en http://127.0.0.1:$DashPort" }
    $dash = "http://127.0.0.1:$DashPort"
    if ((Get-Content $EnvFile -ErrorAction SilentlyContinue) -match '^TELEGRAM_BOT_TOKEN=.+') { Ok "Telegram conectado - escribile a tu bot." }
    Write-Host ""; Write-Host "  Abri:  $dash" -ForegroundColor White
    if (-not $env:RUGOL_NO_OPEN) { Start-Process $dash }  # en auto-arranque no abrimos el navegador
    Write-Host ""; Write-Host "Detener: rugol down  |  Estado: rugol status  |  Logs: rugol logs"
}
function Cmd-Down { Stop-One (Join-Path $RunDir "dashboard.pid") "dashboard"; Stop-One (Join-Path $RunDir "core.pid") "core" }
function Cmd-Restart { Cmd-Down; Start-Sleep 1; Cmd-Up }

function Cmd-Status {
    Write-Host ""; Write-Host "Servicios" -ForegroundColor White
    if (Pid-Running (Join-Path $RunDir "core.pid")) { Ok "core      (pid $(Get-Content (Join-Path $RunDir 'core.pid')))" } else { Warn "core      detenido" }
    if (Pid-Running (Join-Path $RunDir "dashboard.pid")) { Ok "dashboard (pid $(Get-Content (Join-Path $RunDir 'dashboard.pid')))" } else { Warn "dashboard detenido" }
    Write-Host ""; Write-Host "Salud" -ForegroundColor White
    try { Invoke-RestMethod "http://127.0.0.1:$CorePort/api/health" -TimeoutSec 2 | Out-Null; Ok "API -> :$CorePort" } catch { Warn "API -> no responde" }
    try { Invoke-WebRequest "http://127.0.0.1:$DashPort/" -TimeoutSec 2 -UseBasicParsing | Out-Null; Ok "UI  -> :$DashPort" } catch { Warn "UI  -> no responde" }
    Write-Host ""; Write-Host "Home   $HomeDir"
}
function Cmd-Logs {
    $svc = if ($Rest -and $Rest.Count -gt 0) { $Rest[0] } else { "core" }
    $f = if ($svc -in @("dashboard", "dash", "ui")) { Join-Path $LogsDir "dashboard.out.log" } else { Join-Path $LogsDir "core.err.log" }
    if (Test-Path $f) { Get-Content $f -Tail 100 -Wait } else { Warn "sin log todavia: $f" }
}
function Cmd-Doctor {
    Write-Host ""; Write-Host "rugol doctor" -ForegroundColor White
    $fail = 0; $py = Resolve-Python; $node = Resolve-Node
    if ($py) { Ok "python: $(& $py --version 2>&1)" } else { Err "no encontre Python"; $fail = 1 }
    if ($node) { Ok "node: $(& $node --version)" } else { Err "node no disponible"; $fail = 1 }
    if (Have "uv") { Ok "uv presente" } else { Warn "uv no esta (el instalador lo usa)" }
    if (Have "claude") { Ok "claude CLI presente" } else { Warn "claude CLI no esta en PATH (OK si usas API key)" }
    if (Test-Path (Join-Path $AppDir "core\main.py")) { Ok "app en $AppDir" } else { Err "app no encontrada"; $fail = 1 }
    if (Test-Path (Join-Path $DashDir ".next\standalone\server.js")) { Ok "dashboard compilado" } else { Warn "dashboard sin compilar - 'rugol build'" }
    if (Test-Path $EnvFile) {
        Ok "config presente"
        $envc = Get-Content $EnvFile
        if ($envc -match '^USE_SUBSCRIPTION=true') {
            if ($envc -match '^CLAUDE_CODE_OAUTH_TOKEN=.+') { Ok "auth: suscripcion (token presente)" } else { Warn "auth: falta CLAUDE_CODE_OAUTH_TOKEN - re-corre 'rugol setup'"; $fail = 1 }
        } else {
            if ($envc -match '^ANTHROPIC_API_KEY=sk-ant-') { Ok "auth: API key" } else { Warn "auth: API key invalida - re-corre 'rugol setup'"; $fail = 1 }
        }
    } else { Warn "falta config - corre 'rugol setup'" }
    Write-Host ""
    if ($fail -eq 0) { Ok "Todo listo." } else { Err "Resolve lo de arriba antes de 'rugol up'." }
}
function Cmd-Update {
    Require-App
    if (Test-Path (Join-Path $AppDir ".git")) {
        # reset --hard al remoto (no 'pull'): el deploy no debe trabarse por
        # archivos que el runtime escribe. Tus datos viven en $HomeDir.
        git -C $AppDir fetch --depth 1 origin main 2>$null
        git -C $AppDir reset --hard origin/main 2>$null
        Ok "codigo actualizado"
    }
    # Refrescar el launcher en el bin (sin reinstalar a mano).
    $bin = Join-Path $HomeDir "bin"
    if (Test-Path $bin) {
        Copy-Item (Join-Path $AppDir "cli\rugol.ps1") $bin -Force
        Copy-Item (Join-Path $AppDir "cli\rugol.cmd") $bin -Force
        Ok "launcher actualizado"
    }
    $py = Resolve-Python
    if ($py) { Push-Location $AppDir; & $py -m pip install -q -r core/requirements.txt; Pop-Location; Ok "deps backend OK" }
    Build-Dashboard
    Cmd-Restart
    Ok "rugol actualizado. Tus datos en $HomeDir quedaron intactos."
}
function Cmd-Uninstall {
    $ans = Read-Host "Detener rugol y borrar tambien tus DATOS en $HomeDir? [no/si]"
    Cmd-Down
    if ($ans -in @("si", "si", "yes")) { Remove-Item -Recurse -Force $HomeDir; Ok "home borrado" } else { Write-Host "  Datos conservados en $HomeDir" }
}
function Cmd-Open { Start-Process "http://127.0.0.1:$DashPort" }
function Cmd-Version {
    $v = $null; $initf = Join-Path $AppDir "core\__init__.py"
    if (Test-Path $initf) { $m = Select-String -Path $initf -Pattern '__version__\s*=\s*"([^"]+)"' | Select-Object -First 1; if ($m) { $v = $m.Matches[0].Groups[1].Value } }
    if (-not $v) { $v = "(desconocida)" }
    Write-Host "rugol $v"
}
function Cmd-Bot {
    Require-App; Require-Env
    $py = Resolve-Python
    $sub = if ($Rest -and $Rest.Count -gt 0) { $Rest[0].ToLower() } else { "list" }
    Load-DotEnv $EnvFile
    Push-Location $AppDir
    try {
        if ($sub -in @("list", "ls")) {
            & $py "cli\rugol-botctl.py" list
        } elseif ($sub -eq "add") {
            Write-Host ""
            Write-Host "Conectar un bot de Telegram a un proyecto" -ForegroundColor White
            Write-Host "  Crea el bot en @BotFather (/newbot) y pega su token."
            $token = Read-Host "  Token del bot"
            if (-not $token) { Err "Sin token, cancelo."; return }
            $agent = Read-Host "  Agente que responde [assistant]"
            if (-not $agent) { $agent = "assistant" }
            $label = Read-Host "  Nombre/etiqueta (ej. Ventas)"
            $users = Read-Host "  User IDs permitidos (coma-sep, Enter = reusar los del bot 1)"
            & $py "cli\rugol-botctl.py" add "$token" "$agent" "$label" "$users"
        } elseif ($sub -in @("remove", "rm")) {
            $key = if ($Rest.Count -gt 1) { $Rest[1] } else { "" }
            if (-not $key) { Err "Uso: rugol bot remove <key>  (ver 'rugol bot list')"; return }
            & $py "cli\rugol-botctl.py" remove "$key"
        } else { Err "Subcomando desconocido. Uso: rugol bot [list|add|remove <key>]" }
    } finally { Pop-Location }
    if ($sub -in @("add", "remove", "rm")) {
        if (Pid-Running (Join-Path $RunDir "core.pid")) { Write-Host "Reinicio el core para aplicar el cambio..."; Cmd-Restart }
    }
}

function Cmd-Vault {
    Require-App
    $memRoot = Join-Path $AppDir "agent-memory"
    if (-not (Test-Path $memRoot) -or -not (Get-ChildItem $memRoot -ErrorAction SilentlyContinue)) {
        Warn "Todavia no hay memorias. Habla con un agente (Telegram o dashboard) y volve."; return
    }
    $target = $memRoot
    if ($Rest -and $Rest.Count -gt 0) {
        $slug = ($Rest[0].ToLower() -replace '[^a-z0-9]+', '-').Trim('-')
        if (Test-Path (Join-Path $memRoot $slug)) { $target = Join-Path $memRoot $slug }
        else { Warn "No hay memorias para '$($Rest[0])' - abro el vault completo." }
    }
    Write-Host ""
    Write-Host "Vault de memoria: $target" -ForegroundColor White
    Start-Process explorer.exe $target
    Write-Host "  Para ver el grafo: abri Obsidian -> 'Open folder as vault' -> esa carpeta -> Graph view." -ForegroundColor DarkGray
    Write-Host "  Si no tenes Obsidian: instalalo gratis en https://obsidian.md" -ForegroundColor DarkGray
}

function Cmd-Evolve {
    Require-App
    $agent = if ($Rest -and $Rest.Count -gt 0) { $Rest[0] } else { "" }
    if (-not $agent) { Err "Uso: rugol evolve <agente>   (ej. rugol evolve assistant)"; return }
    $base = "http://127.0.0.1:$CorePort"
    try { Invoke-RestMethod "$base/api/health" -TimeoutSec 3 | Out-Null } catch { Err "El core no responde. Corre 'rugol up' primero."; return }
    try { $agents = Invoke-RestMethod "$base/api/agents" } catch { Err "No pude listar los agentes."; return }
    $a = $agents | Where-Object { $_.name -eq $agent } | Select-Object -First 1
    if (-not $a) { Err "No existe el agente '$agent'. Mira la lista en el dashboard."; return }
    $aid = $a.id
    Write-Host ""
    Write-Host "Self-improving - '$agent' propone mejoras a su propio prompt..." -ForegroundColor White
    Write-Host "  (usa Opus; puede tardar ~20-40s)" -ForegroundColor DarkGray
    try { $r = Invoke-RestMethod -Method Post "$base/api/agents/$aid/evolution/propose?max_candidates=2" } catch { Err "La propuesta fallo."; return }
    $ids = $r.proposed_version_ids
    if (-not $ids -or $ids.Count -eq 0) { Write-Host ""; Ok "El agente no propuso cambios (su prompt ya esta solido, o faltan corridas)."; return }
    Write-Host ""; Ok "Propuestas generadas: $($ids -join ', ')"
    try {
        $ev = Invoke-RestMethod "$base/api/agents/$aid/evolution"
        foreach ($v in $ev.versions) { if ($v.status -eq "proposed") { Write-Host ("  - " + $v.id + "  -  " + $v.hypothesis) } }
    } catch {}
    Write-Host ""
    Write-Host "Vos decidis. Revisa, valida y acepta/rechaza en:" -ForegroundColor White
    Write-Host "  http://127.0.0.1:$DashPort/agents/$aid/evolution"
    Write-Host "  Nada se aplica solo: el humano siempre tiene la decision final." -ForegroundColor DarkGray
}

function Cmd-Sessions {
    Require-App
    $py = Resolve-Python
    & $py (Join-Path $AppDir "cli\rugol-sessions.py") @Rest
}

function Cmd-Autostart {
    $action = if ($Rest -and $Rest.Count -gt 0) { $Rest[0].ToLower() } else { "on" }
    $task = "Rugol Autostart"
    $cmd = Join-Path $HomeDir "bin\rugol.cmd"
    if ($action -in @("on", "enable")) {
        # En Windows los procesos de Start-Process sobreviven al padre, asi que
        # alcanza con correr 'up' al iniciar sesion (no hace falta supervisor).
        # cmd.exe setea RUGOL_NO_OPEN para no abrir el navegador en cada logon.
        $arg = "/c set RUGOL_NO_OPEN=1 && `"$cmd`" up"
        $a = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $arg
        $t = New-ScheduledTaskTrigger -AtLogOn
        $s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
        try {
            Register-ScheduledTask -TaskName $task -Action $a -Trigger $t -Settings $s -Force -ErrorAction Stop | Out-Null
            Ok "auto-arranque activado - Rugol se levanta al iniciar sesion."
            Write-Host "  Quitarlo: rugol autostart off" -ForegroundColor DarkGray
        } catch { Err "no pude crear la tarea programada: $_" }
    } elseif ($action -in @("off", "disable")) {
        Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue
        Ok "auto-arranque desactivado."
    } else {
        if (Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue) { Ok "auto-arranque: ACTIVADO" } else { Warn "auto-arranque: desactivado" }
    }
}

function Show-Usage {
@"

rugol - tu orquestador de agentes Claude, en un comando. Sin Docker.

Uso:  rugol <comando>

  setup        Configuracion inicial (auth + modelo + Telegram)
  up           Levanta core + dashboard y abre el navegador
  down         Detiene todo
  restart      Reinicia
  status       Estado de servicios y salud
  logs [svc]   Logs en vivo (core | dashboard)
  doctor       Verifica runtime, puertos y configuracion
  build        (Re)compila el dashboard
  open         Abre el dashboard
  update       Actualiza el codigo y reconstruye (datos intactos)
  uninstall    Quita rugol (pregunta si borrar datos)

Agentes y memoria:
  bot [list|add|remove]  Bots de Telegram por proyecto (uno por agente)
  vault [agente]         Abre la memoria como vault de Obsidian
  evolve <agente>        Self-improving: el agente propone mejorar su prompt
  sessions [filtro]      Tus sesiones de Claude Code + como retomarlas
  autostart [on|off]     Levanta Rugol solo al iniciar sesion

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
    "uninstall" { Cmd-Uninstall }
    { $_ -in @("bot", "bots") }         { Cmd-Bot }
    { $_ -in @("vault", "memory", "mem") } { Cmd-Vault }
    { $_ -in @("evolve", "improve") }   { Cmd-Evolve }
    { $_ -in @("sessions", "ses") }     { Cmd-Sessions }
    "autostart"                         { Cmd-Autostart }
    { $_ -in @("version", "--version", "-v") } { Cmd-Version }
    default   { Show-Usage }
}
