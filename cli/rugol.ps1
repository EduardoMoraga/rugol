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

# .Es NUESTRO core el que contesta en el puerto?
#
# "algo respondio" no es "el core arranco". Si el puerto lo tiene otra
# aplicacion, su 200 pasa por sano y 'rugol up' canta verde con el core caido
# (medido en vivo en Mac, y aca es peor: Start-Backend ni siquiera miraba si el
# puerto estaba tomado). La unica prueba que sirve es la marca del core
# (core/api/health.py: SERVICE_ID).
function Core-Responds([int]$Port = 0) {
    if ($Port -eq 0) { $Port = $CorePort }
    try {
        $r = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 5 -MaximumRedirection 0 -ErrorAction Stop
        return ($r.service -eq "rugol-core")
    } catch { return $false }
}
# .Hay algo escuchando en el puerto que NO es el core?
function Port-Taken([int]$Port) {
    try { return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop) }
    catch { return $false }
}

function Wait-Health([int]$Tries = 30) {
    Write-Host -NoNewline "  esperando al core"
    for ($i = 0; $i -lt $Tries; $i++) {
        if (Core-Responds) { Write-Host ""; return $true }
        Write-Host -NoNewline "."; Start-Sleep 1
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
# Rotacion de logs. Un asistente 24/7 escribe sin parar: se encontro un
# core.log de 143 MB en una instalacion de dos meses. Rotamos al arrancar
# (simple, sin dependencias) y conservamos una generacion.
function Rotate-Log($file, $maxMB = 50) {
    if (-not (Test-Path $file)) { return }
    $mb = [math]::Round((Get-Item $file).Length / 1MB)
    if ($mb -ge $maxMB) {
        Move-Item $file "$file.1" -Force -ErrorAction SilentlyContinue
        Warn "log rotado ($mb MB): $(Split-Path $file -Leaf)"
    }
}

function Start-Backend {
    $py = Resolve-Python
    # Si el puerto ya lo tiene un core nuestro sano, lo ADOPTAMOS. Si lo tiene
    # otra cosa, uvicorn no va a poder bindear y el usuario terminaba viendo
    # "core saludable" por la respuesta de esa otra app: mejor parar aca.
    if (Core-Responds) { return $true }
    if (Port-Taken $CorePort) {
        Warn "el puerto $CorePort esta ocupado por otro programa - no lo toco"
        return $false
    }
    New-Item -ItemType Directory -Force -Path $RunDir, $LogsDir | Out-Null
    Rotate-Log (Join-Path $LogsDir "core.out.log")
    Rotate-Log (Join-Path $LogsDir "core.err.log")
    Load-DotEnv $EnvFile
    $env:AGENTS_DIR = Join-Path $HomeDir "agents"
    $env:SKILLS_DIR = Join-Path $HomeDir "skills"
    # Todo el estado mutable (DB, jobstore del scheduler, settings.json,
    # adjuntos) vive aca, fuera de $AppDir: reinstalar borra el codigo, nunca
    # tus datos. Antes settings.json y scheduler.db vivian con el codigo.
    $env:RUGOL_DATA_DIR = $DataDir
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
    return $true
}
function Start-Dashboard {
    $node = Resolve-Node
    Rotate-Log (Join-Path $LogsDir "dashboard.out.log")
    Rotate-Log (Join-Path $LogsDir "dashboard.err.log")
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

# Copia los .md de una carpeta de plantillas a la del usuario, solo si la
# destino esta vacia. Silenciosa cuando no hay nada que copiar.
function Seed-Dir([string]$Src, [string]$Dst, [string]$Label) {
    if (-not (Test-Path $Src)) { return }
    if (Get-ChildItem $Dst -ErrorAction SilentlyContinue) { return }
    $files = @(Get-ChildItem (Join-Path $Src "*.md") -File -ErrorAction SilentlyContinue)
    if ($files.Count -eq 0) { return }
    $files | Copy-Item -Destination $Dst -Force
    Ok "$Label copiados a $Dst ($($files.Count))"
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
    # Semillas opcionales. Solo .md: las carpetas del repo arrancan vacias a
    # proposito (el catalogo de templates vive en core/templates/catalog.py y se
    # clona con un click desde /projects). Antes copiabamos el directorio
    # entero -incluido el .gitkeep- y anunciabamos "Agentes de ejemplo
    # copiados" en una instalacion que se quedaba con cero agentes.
    Seed-Dir (Join-Path $AppDir "agents-templates") (Join-Path $HomeDir "agents") "Agentes de ejemplo"
    Seed-Dir (Join-Path $AppDir "skills-templates") (Join-Path $HomeDir "skills") "Skills de ejemplo"

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
        # El token es OPCIONAL. Si dejas esto vacio, Rugol usa el login de esta
        # maquina (~/.claude) y lo conectas despues con 'rugol login' - que es
        # el camino recomendado en un PC de escritorio. El token solo hace
        # falta headless (un server sin sesion interactiva).
        Write-Host "   Podes dejarlo vacio y conectar la cuenta despues con 'rugol login'."
        Write-Host "   El token long-lived solo hace falta headless (server sin login)."
        $sec = Read-Host "   Token de suscripcion (Enter para usar el login de esta maquina)" -AsSecureString
        $oauthToken = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
    }

    Write-Host ""
    Write-Host "2) Modelo por defecto (Rugol enruta solo por tarea; este es el fallback)"
    Write-Host "   [1] Sonnet 5 (recomendado)   [2] Opus 5   [3] Haiku 4.5"
    $modelChoice = Read-Host "   Opcion [1]"
    switch ($modelChoice) { "2" { $model = "claude-opus-5" } "3" { $model = "claude-haiku-4-5" } default { $model = "claude-sonnet-5" } }

    Write-Host ""
    Write-Host "3) Telegram (opcional - Enter para saltar)"
    $tgToken = Read-Host "   TELEGRAM_BOT_TOKEN"
    $tgUsers = ""; if ($tgToken) { $tgUsers = Read-Host "   User IDs permitidos (coma-separado)" }

    Write-Host ""
    Write-Host "4) Agente por defecto (responde al instante, sin /bind)"
    $defaultAgent = Read-Host "   Agente por defecto [assistant]"; if (-not $defaultAgent) { $defaultAgent = "assistant" }

    $secret = -join ((1..32) | ForEach-Object { '{0:x}' -f (Get-Random -Max 16) })
    $stamp  = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    if (Test-Path $EnvFile) {
        # Ya habia configuracion: tocamos SOLO lo que el usuario acaba de
        # contestar. El .env acepta unas 40 claves y setup pregunta por ocho;
        # reescribir el archivo entero borraba OPENAI_API_KEY, CODEX_*,
        # SAFETY_*, HONCHO_*, TELEGRAM_BOTS (los bots multiproyecto que este
        # wizard ni siquiera pregunta) y rotaba el SESSION_SECRET.
        $kv = @(
            "USE_SUBSCRIPTION=$useSub",
            "DEFAULT_MODEL=$model",
            "DEFAULT_AGENT=$defaultAgent",
            "CORE_PORT=$CorePort",
            "DASHBOARD_PORT=$DashPort"
        )
        # Credenciales: solo las que escribio. Vaciarlas porque apreto Enter
        # seria desconectarle la cuenta que puso con 'rugol login'.
        if ($apiKey)     { $kv += "ANTHROPIC_API_KEY=$apiKey" }
        if ($oauthToken) { $kv += "CLAUDE_CODE_OAUTH_TOKEN=$oauthToken" }
        # Telegram: "Enter para saltar" tiene que SALTAR, no borrar tus bots.
        if ($tgToken) { $kv += @("TELEGRAM_BOT_TOKEN=$tgToken", "TELEGRAM_ALLOWED_USERS=$tgUsers") }
        Invoke-Auth (@("env-set") + $kv) | Out-Null
        Write-Host ""; Ok "Configuracion guardada en $EnvFile"
        if ((Pid-Running (Join-Path $RunDir "core.pid")) -or (Pid-Running (Join-Path $RunDir "dashboard.pid"))) {
            Write-Host ""; Write-Host "Rugol estaba corriendo - lo reinicio para aplicar la nueva configuracion..."; Cmd-Restart
        }
        return
    }
    # Primera vez: el archivo completo, con los comentarios que explican cada
    # clave. Es el unico momento en que setup manda sobre el archivo entero.
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
    } else {
        Write-Host ""
        if ($useSub -eq "true" -and -not $oauthToken) { Write-Host "Siguiente:  rugol login  ->  rugol up" }
        else { Write-Host "Siguiente:  rugol up" }
    }
}

# __ auth: login / logout / status ____________________________________________
# La logica vive en cli/rugol-auth.py (un solo lugar para Windows y Mac/Linux).
# El script edita el .env clave por clave: 'rugol login' NO te vuelve a
# preguntar modelo ni token de Telegram, al contrario de 'rugol setup'.
function Invoke-Auth([string[]]$AuthArgs) {
    $script:AuthOk = $false
    $py = Resolve-Python
    $s  = Join-Path $AppDir "cli\rugol-auth.py"
    if (-not (Test-Path (Join-Path $AppDir "core\main.py"))) { Err "no encuentro la app en $AppDir"; return }
    if (-not $py) { Err "no encontre Python - reinstala con el one-liner del README"; return }
    if (-not (Test-Path $s)) { Err "falta cli\rugol-auth.py - corre 'rugol update'"; return }
    $env:RUGOL_HOME = $HomeDir
    if (-not $env:RUGOL_DATA_DIR) { $env:RUGOL_DATA_DIR = $DataDir }
    & $py $s @AuthArgs
    $script:AuthOk = ($LASTEXITCODE -eq 0)
}

function Cmd-Login  { Invoke-Auth (@("login") + @($Rest | Where-Object { $_ })) }
function Cmd-Logout { Invoke-Auth @("logout") }
function Cmd-Auth {
    # 'rugol auth' -> status; 'rugol auth --verify' -> status --verify.
    if (-not $Rest -or $Rest.Count -eq 0) { Invoke-Auth @("status"); return }
    if ($Rest[0].StartsWith("-")) { Invoke-Auth (@("status") + $Rest) } else { Invoke-Auth $Rest }
}

function Cmd-Build { Build-Dashboard }

# El puerto del core queda HORNEADO en el build: next.config.ts lee
# NEXT_PUBLIC_API_URL al compilar y Next lo serializa en routes-manifest.json.
# Cambiar CORE_PORT en el .env -lo que dice el troubleshooting cuando el 8000
# esta ocupado- movia el core y dejaba al dashboard hablandole al puerto viejo:
# todas las paginas rotas, sin un mensaje que lo explicara.
function Dashboard-ApiPort {
    $m = Join-Path $DashDir ".next\routes-manifest.json"
    if (-not (Test-Path $m)) { return 0 }
    $hit = Select-String -Path $m -Pattern '"destination":"http://127\.0\.0\.1:(\d+)' -AllMatches |
           Select-Object -First 1
    if (-not $hit) { return 0 }
    return [int]$hit.Matches[0].Groups[1].Value
}
# Recompila si el build apunta a otro puerto. $true si recompilo.
function Rebuild-IfPortChanged {
    $baked = Dashboard-ApiPort
    if ($baked -eq 0 -or $baked -eq $CorePort) { return $false }
    Warn "el dashboard fue compilado contra el puerto $baked y el core ahora usa $CorePort"
    Write-Host "  Recompilo para que el dashboard le hable al core correcto."
    Build-Dashboard
    return [bool]$script:BuildOk
}

function Cmd-Up {
    Require-App; Require-Env
    Write-Host ""
    if (-not (Test-Path (Join-Path $DashDir ".next\standalone\server.js"))) { Build-Dashboard; if (-not $script:BuildOk) { Err "No pude preparar el dashboard."; exit 1 } }
    elseif (Rebuild-IfPortChanged) { Stop-One (Join-Path $RunDir "dashboard.pid") "dashboard viejo" }
    if (Pid-Running (Join-Path $RunDir "core.pid")) { Ok "core ya estaba corriendo" }
    else {
        Write-Host "Levantando el core..."
        # Start-Backend devuelve $false cuando el puerto lo tiene otro programa.
        # Seguir de largo era el bug: el dashboard arrancaba contra un core
        # inexistente y el usuario leia "core saludable" por la otra app.
        if (-not (Start-Backend)) {
            Err "No levante el core: el puerto $CorePort lo tiene otro programa."
            Write-Host "    Cerralo, o cambia CORE_PORT en $EnvFile y corre 'rugol up' de nuevo."
            exit 1
        }
        if (Wait-Health 30) { Ok "core saludable en http://127.0.0.1:$CorePort" }
        else {
            Err "El core no respondio en 30s - no arranco el dashboard contra un core caido."
            Write-Host "    Mira:  rugol logs core"
            exit 1
        }
    }
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
    if (Core-Responds) { Ok "API -> :$CorePort" }
    elseif (Port-Taken $CorePort) { Warn "API -> el puerto $CorePort responde, pero NO es el core de Rugol (otra app lo tiene)" }
    else { Warn "API -> no responde" }
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
        # Auth de verdad: le preguntamos al CLI de Claude que Rugol realmente
        # ejecuta. Antes esto era un match sobre el .env - un token vencido
        # pasaba el doctor y despues fallaba cada run.
        # --verify hace una llamada real al API: es la unica forma honesta de
        # saber si la credencial sirve ('auth status' reporta un token revocado
        # como conectado). Cuesta una fraccion de centavo y tarda ~2s.
        Write-Host "  verificando la cuenta de Claude contra el API..." -ForegroundColor DarkGray
        Invoke-Auth @("status", "--json", "--verify") | Out-Null
        if ($script:AuthOk) { Ok "auth: cuenta de Claude verificada" }
        else { Warn "auth: la cuenta de Claude no funciona - 'rugol auth --verify' para el detalle, 'rugol login' para arreglarlo"; $fail = 1 }
    } else { Warn "falta config - corre 'rugol setup'" }
    Write-Host ""
    if ($fail -eq 0) { Ok "Todo listo." } else { Err "Resolve lo de arriba antes de 'rugol up'." }
}
function Cmd-Update {
    Require-App
    $fetched = $false
    if (Test-Path (Join-Path $AppDir ".git")) {
        # reset --hard al remoto (no 'pull'): el deploy no debe trabarse por
        # archivos que el runtime escribe. Tus datos viven en $HomeDir.
        git -C $AppDir fetch --depth 1 origin main 2>$null
        if ($LASTEXITCODE -eq 0) {
            git -C $AppDir reset --hard origin/main 2>$null | Out-Null
            $fetched = $true
            Ok "codigo actualizado"
        } else {
            Warn "no pude bajar la ultima version (red caida o GitHub inaccesible) - reintenta 'rugol update' en un rato. Sigo con lo instalado."
        }
    }
    # Refrescar el launcher en el bin (sin reinstalar a mano).
    $bin = Join-Path $HomeDir "bin"
    if ($fetched -and (Test-Path $bin)) {
        Copy-Item (Join-Path $AppDir "cli\rugol.ps1") $bin -Force
        Copy-Item (Join-Path $AppDir "cli\rugol.cmd") $bin -Force
        Ok "launcher actualizado"
    }
    # Deps: el venv lo crea uv (SIN pip) - instalar con uv.
    $py = Resolve-Python
    if ((Have "uv") -and $py) {
        uv pip install --python $py -q -r (Join-Path $AppDir "core\requirements.txt")
        if ($LASTEXITCODE -eq 0) { Ok "deps backend OK" } else { Warn "deps no actualizadas (seguis con las actuales)" }
    } elseif ($py) {
        & $py -m pip --version 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            & $py -m pip install -q -r (Join-Path $AppDir "core\requirements.txt")
            if ($LASTEXITCODE -eq 0) { Ok "deps backend OK" } else { Warn "deps no actualizadas" }
        } else { Warn "no pude actualizar deps (sin uv ni pip) - el backend sigue con las actuales" }
    }
    # Apagar ANTES de compilar: en Windows el server bloquea archivos de .next
    # y el build/copia falla a medias (dashboard sin estilos). Down -> build -> up.
    Cmd-Down
    Build-Dashboard
    Cmd-Up
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
    if (-not (Core-Responds)) { Err "El core no responde. Corre 'rugol up' primero."; return }
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
        # Ventana oculta + RUGOL_NO_OPEN para no molestar. 'up' es idempotente
        # (si ya corre, no hace nada), asi que ademas del arranque al logon
        # agregamos un WATCHDOG cada 5 min: si el proceso se cayo, lo revive.
        # Equivalente al supervisor launchd de Mac.
        $arg = "-NoProfile -WindowStyle Hidden -Command `"`$env:RUGOL_NO_OPEN='1'; & '$cmd' up`""
        $a = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg
        # AtStartup (no AtLogOn): si la maquina se reinicia por un corte de luz
        # y nadie entra por RDP, con AtLogOn Rugol NO vuelve. Con S4U la tarea
        # corre en el contexto del usuario sin pedir contrasena, asi que el
        # login de Claude en %USERPROFILE%\.claude sigue disponible.
        $t1 = New-ScheduledTaskTrigger -AtStartup
        $t2 = New-ScheduledTaskTrigger -AtLogOn
        # Watchdog: 'up' es idempotente, asi que reintentarlo cada 5 min revive
        # el servicio si se cayo, sin molestar si esta sano.
        $t3 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
            -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
        $s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -StartWhenAvailable -Hidden -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
            -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)
        $p = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited
        try {
            Register-ScheduledTask -TaskName $task -Action $a -Trigger @($t1, $t2, $t3) `
                -Settings $s -Principal $p -Force -ErrorAction Stop | Out-Null
            Ok "auto-arranque activado - levanta al ENCENDER la maquina (no hace falta iniciar sesion)."
            Ok "watchdog cada 5 min: si el servicio se cae, vuelve solo."
            Write-Host "  Quitarlo: rugol autostart off" -ForegroundColor DarkGray
        } catch {
            Warn "no pude registrar la tarea con arranque al boot ($_)"
            Write-Host "  Reintento con el modo simple (al iniciar sesion)..." -ForegroundColor DarkGray
            try {
                Register-ScheduledTask -TaskName $task -Action $a -Trigger @($t2, $t3) `
                    -Settings $s -Force -ErrorAction Stop | Out-Null
                Ok "auto-arranque activado (al iniciar sesion + watchdog)."
                Warn "OJO: si la maquina reinicia y nadie entra, Rugol no vuelve solo."
            } catch { Err "no pude crear la tarea programada: $_" }
        }
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
  login        Conecta tu cuenta de Claude (--token headless - --api-key)
  logout       Desconecta la cuenta y limpia credenciales del .env
  auth         Estado real de la cuenta (cuenta, plan, credencial en uso)
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
    "login"   { Cmd-Login }
    "logout"  { Cmd-Logout }
    "auth"    { Cmd-Auth }
    { $_ -in @("bot", "bots") }         { Cmd-Bot }
    { $_ -in @("vault", "memory", "mem") } { Cmd-Vault }
    { $_ -in @("evolve", "improve") }   { Cmd-Evolve }
    { $_ -in @("sessions", "ses") }     { Cmd-Sessions }
    "autostart"                         { Cmd-Autostart }
    { $_ -in @("version", "--version", "-v") } { Cmd-Version }
    default   { Show-Usage }
}
