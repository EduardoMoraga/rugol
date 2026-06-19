// Rugol — app de escritorio.
//
// Envuelve la PLATAFORMA REAL de Rugol (FastAPI + dashboard Next) en una app
// nativa, transferible. Al arrancar:
//   1) levanta el backend (Python EMPAQUETADO + claude embebido en el SDK),
//      usando la suscripción de Anthropic del usuario,
//   2) levanta el dashboard (build standalone de Next, corrido con el Node de
//      Electron — sin Node externo),
//   3) carga el dashboard en una ventana.
// No hay terminal, no hay Docker, no requiere Python instalado. Es el Rugol
// completo: Architect, Asistente de config, agentes con Soul/Memory/Tools/MCP,
// ontología, self-improving.

const { app, BrowserWindow, Menu, shell, nativeTheme, ipcMain, dialog } = require("electron");
const path = require("node:path");
const fs = require("node:fs");
const net = require("node:net");
const http = require("node:http");
const { spawn } = require("node:child_process");

const PACKAGED = app.isPackaged;
const PAYLOAD = PACKAGED ? path.join(process.resourcesPath, "payload") : null;

// Marca por variante (Rugol / Rugol CRM / Rugol HRO). El build script escribe
// payload/brand.json; en dev se puede forzar con RUGOL_VARIANT=crm|hro.
function loadBrand() {
  const def = { id: "Rugol", name: "Rugol", accent: "#6366f1", accentStrong: "#818cf8", tagline: "" };
  try {
    const f = PACKAGED ? path.join(PAYLOAD, "brand.json")
      : path.join(__dirname, "variants", (process.env.RUGOL_VARIANT || "rugol"), "brand.json");
    if (require("node:fs").existsSync(f)) return { ...def, ...JSON.parse(require("node:fs").readFileSync(f, "utf8")) };
  } catch { /* noop */ }
  return def;
}
const BRAND = loadBrand();
const APP_NAME = BRAND.name;
// userData aislado por variante (evita que Rugol/CRM/HRO compartan DB y estado).
try { app.setName(BRAND.id); } catch { /* noop */ }

let backendProc = null;
let dashProc = null;
let proxyServer = null;
let mainWindow = null;
let dashUrl = null;

function log(...a) { console.log("[rugol-desktop]", ...a); }
function safeExists(p) { try { return fs.existsSync(p); } catch { return false; } }

// Directorio de trabajo ESCRIBIBLE. Empaquetado: copia la fuente del payload
// (read-only) a userData en el primer arranque y corre desde ahí — así REPO_ROOT
// (que el backend calcula relativo a core/) queda escribible (DB, memoria, logs,
// agentes nuevos del Architect). Dev: corre desde el repo.
function resolveWorkingDir() {
  if (!PACKAGED) return path.join(__dirname, "..");
  const work = path.join(app.getPath("userData"), "platform");
  if (!safeExists(path.join(work, "core", "main.py"))) {
    log("primer arranque: copiando plataforma a", work);
    fs.mkdirSync(work, { recursive: true });
    fs.cpSync(path.join(PAYLOAD, "rugol-src"), work, { recursive: true });
  }
  for (const d of ["data", "logs", "agent-soul", "agent-memory", "workspace"]) {
    try { fs.mkdirSync(path.join(work, d), { recursive: true }); } catch { /* noop */ }
  }
  return work;
}

function pyExecutable() {
  if (PACKAGED) return path.join(PAYLOAD, "python", "bin", "python3.12");
  const venv = path.join(__dirname, "..", ".venv", "bin", "python");
  if (safeExists(venv)) return venv;
  return "python3.12";
}

function dashboardServerJs() {
  if (PACKAGED) return path.join(PAYLOAD, "dashboard", "server.js");
  return path.join(__dirname, "..", "dashboard", ".next", "standalone", "server.js");
}

function getFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => { const p = srv.address().port; srv.close(() => resolve(p)); });
  });
}

function waitForHttp(url, { timeoutMs = 90000, intervalMs = 500 } = {}) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = require("node:http").get(url, (res) => { res.destroy(); resolve(true); });
      req.on("error", () => {
        if (Date.now() - started > timeoutMs) reject(new Error("timeout esperando " + url));
        else setTimeout(tick, intervalMs);
      });
      req.setTimeout(3000, () => req.destroy());
    };
    tick();
  });
}

async function startBackend(port, workingDir) {
  const py = pyExecutable();
  const env = {
    ...process.env,
    USE_SUBSCRIPTION: "true",        // usa la cuenta Anthropic (Pro/Max/Team)
    PYTHONUNBUFFERED: "1",
    CORE_PORT: String(port),
    RUGOL_BRAND_NAME: BRAND.name,
    RUGOL_BRAND_ACCENT: BRAND.accent || "",
    RUGOL_BRAND_ACCENT_STRONG: BRAND.accentStrong || "",
    RUGOL_BRAND_TAGLINE: BRAND.tagline || "",
    RUGOL_VARIANT: BRAND.variant || "rugol",
  };
  delete env.ANTHROPIC_API_KEY;      // que una key del entorno no pise la suscripción
  // Token de suscripción headless si el usuario inició sesión en la app (friend-auth)
  const tok = readStoredToken();
  if (tok) env.CLAUDE_CODE_OAUTH_TOKEN = tok;
  log("backend:", py, "cwd=", workingDir, "port", port);
  backendProc = spawn(py, ["-m", "uvicorn", "core.main:app", "--host", "127.0.0.1", "--port", String(port)],
    { cwd: workingDir, env, stdio: ["ignore", "pipe", "pipe"] });
  backendProc.stdout.on("data", (d) => log("be:", d.toString().trim()));
  backendProc.stderr.on("data", (d) => log("be:", d.toString().trim()));
  backendProc.on("exit", (c) => log("backend exit", c));
  await waitForHttp(`http://127.0.0.1:${port}/api/health`, { timeoutMs: 120000 });
  log("backend listo en", port);
}

async function startDashboard(port, backendPort) {
  const serverJs = dashboardServerJs();
  if (!safeExists(serverJs)) throw new Error("falta el dashboard: " + serverJs);
  const env = {
    ...process.env,
    PORT: String(port),
    HOSTNAME: "127.0.0.1",
    NEXT_PUBLIC_API_URL: `http://127.0.0.1:${backendPort}`,
  };
  // Empaquetado: usar el node REAL embebido (no muestra ícono en el Dock).
  // Dev: usar el node de Electron vía ELECTRON_RUN_AS_NODE.
  let nodeBin = process.execPath;
  if (PACKAGED) {
    const bundledNode = path.join(PAYLOAD, "node", "node");
    if (safeExists(bundledNode)) nodeBin = bundledNode;
    else env.ELECTRON_RUN_AS_NODE = "1"; // fallback si faltara el node embebido
  } else {
    env.ELECTRON_RUN_AS_NODE = "1";
  }
  log("dashboard:", serverJs, "port", port, "→ api", backendPort, "node:", nodeBin);
  dashProc = spawn(nodeBin, [serverJs], { cwd: path.dirname(serverJs), env, stdio: ["ignore", "pipe", "pipe"] });
  dashProc.stdout.on("data", (d) => log("dash:", d.toString().trim()));
  dashProc.stderr.on("data", (d) => log("dash:", d.toString().trim()));
  dashProc.on("exit", (c) => log("dashboard exit", c));
  await waitForHttp(`http://127.0.0.1:${port}/architect`, { timeoutMs: 60000 });
  log("dashboard listo en", port);
}

// Reverse-proxy in-process: /api/* → backend, resto → dashboard. Resuelve los
// puertos en RUNTIME (Next hornea el destino de sus rewrites en build-time, así
// que no se puede confiar en su proxy). Same-origin → las llamadas relativas
// /api del cliente caen acá y van al backend EMPAQUETADO correcto.
function startProxy(proxyPort, dashPort, backendPort) {
  proxyServer = http.createServer((req, res) => {
    const isApi = req.url.startsWith("/api");
    const target = isApi ? backendPort : dashPort;
    const pr = http.request(
      { hostname: "127.0.0.1", port: target, path: req.url, method: req.method, headers: { ...req.headers, host: `127.0.0.1:${target}` } },
      (pres) => { res.writeHead(pres.statusCode || 502, pres.headers); pres.pipe(res); }
    );
    pr.on("error", () => { try { res.writeHead(502); res.end("rugol proxy: upstream error"); } catch { /* noop */ } });
    req.pipe(pr);
  });
  return new Promise((resolve, reject) => {
    proxyServer.on("error", reject);
    proxyServer.listen(proxyPort, "127.0.0.1", () => { log("proxy listo en", proxyPort, "→ api:", backendPort, "ui:", dashPort); resolve(); });
  });
}

// --- Token de suscripción guardado (friend-auth headless), en userData ---
function tokenFile() { return path.join(app.getPath("userData"), "auth.json"); }
function readStoredToken() {
  try { const j = JSON.parse(fs.readFileSync(tokenFile(), "utf8")); return j.subToken || ""; } catch { return ""; }
}

function splash() {
  const a = BRAND.accent || "#2f6e8f";
  return "data:text/html;charset=utf-8," + encodeURIComponent(`<!doctype html><meta charset="utf-8"><style>
    html,body{margin:0;height:100%}body{display:flex;flex-direction:column;gap:16px;align-items:center;justify-content:center;
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0e14;color:#e8eef7}
    .m{width:60px;height:60px;border-radius:16px;background:${a};display:grid;place-items:center;color:#fff;font-weight:800;font-size:30px;
    box-shadow:0 12px 32px ${a}66;animation:p 1.5s ease-in-out infinite}
    .n{font-weight:700;font-size:20px;letter-spacing:-.02em}.s{font-size:12.5px;color:#7d8aa0}
    @keyframes p{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}</style>
    <div class="m">R</div><div class="n">${APP_NAME}</div><div class="s">Levantando la plataforma agéntica…</div>`);
}
function errorPage(msg) {
  return "data:text/html;charset=utf-8," + encodeURIComponent(
    `<!doctype html><meta charset="utf-8"><style>body{font-family:-apple-system,sans-serif;background:#0a0e14;color:#e8eef7;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;gap:10px;text-align:center;padding:40px}h1{color:#e0654b}code{color:#7d8aa0;font-size:12px;white-space:pre-wrap;max-width:80ch}</style><h1>${APP_NAME} no pudo arrancar</h1><code>${String(msg)}</code>`);
}

async function createWindow() {
  nativeTheme.themeSource = "dark";
  mainWindow = new BrowserWindow({
    width: 1440, height: 920, minWidth: 1080, minHeight: 700,
    title: APP_NAME, backgroundColor: "#fbf9f4",
    titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "default",
    show: false,
    webPreferences: { preload: path.join(__dirname, "preload.cjs"), contextIsolation: true, nodeIntegration: false, sandbox: false },
  });
  mainWindow.loadURL(splash());
  mainWindow.once("ready-to-show", () => mainWindow.show());
  try {
    const workingDir = resolveWorkingDir();
    const backendPort = await getFreePort();
    await startBackend(backendPort, workingDir);
    const dashPort = await getFreePort();
    await startDashboard(dashPort, backendPort);
    const proxyPort = await getFreePort();
    await startProxy(proxyPort, dashPort, backendPort);
    dashUrl = `http://127.0.0.1:${proxyPort}`;
    await mainWindow.loadURL(dashUrl);
  } catch (e) {
    log("ERROR arranque:", e.message);
    await mainWindow.loadURL(errorPage(e.message));
  }
  mainWindow.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: "deny" }; });
  mainWindow.on("closed", () => { mainWindow = null; });
}

function killChildren() {
  try { if (proxyServer) proxyServer.close(); } catch { /* noop */ }
  for (const p of [backendProc, dashProc]) { if (p && !p.killed) { try { p.kill("SIGTERM"); } catch { /* noop */ } } }
  setTimeout(() => { for (const p of [backendProc, dashProc]) { if (p && !p.killed) { try { p.kill("SIGKILL"); } catch { /* noop */ } } } }, 1500);
}

function buildMenu() {
  const isMac = process.platform === "darwin";
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    ...(isMac ? [{ role: "appMenu" }] : []),
    { label: APP_NAME, submenu: [
      { label: "Inicio", accelerator: "CmdOrCtrl+1", click: () => mainWindow && dashUrl && mainWindow.loadURL(dashUrl) },
      { type: "separator" }, { role: "reload" }, { role: "forceReload" }, { role: "toggleDevTools" },
      { type: "separator" }, isMac ? { role: "close" } : { role: "quit" },
    ] },
    { role: "editMenu" }, { role: "windowMenu" },
  ]));
}

// Selector nativo de carpeta para conectar una fuente de CVs a una búsqueda.
ipcMain.handle("rugol:pickFolder", async () => {
  const r = await dialog.showOpenDialog(mainWindow, { properties: ["openDirectory"], title: "Conecta una carpeta de CVs" });
  return r.canceled || !r.filePaths.length ? null : r.filePaths[0];
});

app.whenReady().then(() => { buildMenu(); createWindow(); app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); }); });
app.on("window-all-closed", () => { killChildren(); if (process.platform !== "darwin") app.quit(); });
app.on("before-quit", killChildren);
process.on("exit", killChildren);
