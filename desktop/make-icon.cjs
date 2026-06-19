// Ícono por variante: tile de color de marca + "R" + emblema del dominio.
// Uso: electron make-icon.cjs <rugol|crm|hro>  → assets/icon-<v>.icns + .png
const { app, BrowserWindow } = require("electron");
const fs = require("node:fs"); const path = require("node:path"); const { execFileSync } = require("node:child_process");
app.disableHardwareAcceleration();

const V = (process.argv.find((a) => ["rugol", "crm", "hro"].includes(a))) || "rugol";
const BRANDS = {
  // color, sombra, emblema (SVG stroke blanco)
  rugol: { c: "#dd4524", s: "rgba(221,69,36,.34)", em: `<circle cx="6" cy="7" r="2"/><circle cx="18" cy="8" r="2"/><circle cx="12" cy="17" r="2"/><path d="M8 7.5 16 8M16.7 9.5 13 15.2M9.6 15.4 7.2 8.8"/>` },
  crm:   { c: "#2f6e8f", s: "rgba(47,110,143,.34)", em: `<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2.6"/><path d="M12 1v4M12 19v4M1 12h4M19 12h4"/>` },
  hro:   { c: "#7a5cc0", s: "rgba(122,92,192,.34)", em: `<circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0"/><circle cx="17.5" cy="9.5" r="2.5"/><path d="M15 20a5.5 5.5 0 0 1 6.5-5.4"/>` },
};
const B = BRANDS[V];
const ASSETS = path.join(__dirname, "assets"); const ICONSET = path.join(ASSETS, `icon-${V}.iconset`);
const EMBLEM = `<svg width="150" height="150" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.92">${B.em}</svg>`;
const HTML = `data:text/html;charset=utf-8,${encodeURIComponent(`<!doctype html><meta charset="utf-8"><style>
  html,body{margin:0;width:1024px;height:1024px;overflow:hidden}
  .bg{width:1024px;height:1024px;display:flex;align-items:center;justify-content:center;background:#0a0e14}
  .tile{position:relative;width:752px;height:752px;border-radius:184px;display:flex;align-items:center;justify-content:center;background:${B.c};box-shadow:0 44px 120px ${B.s}}
  .r{font-family:Inter,-apple-system,Helvetica,Arial,sans-serif;font-weight:800;font-size:520px;color:#fff;line-height:1;margin-top:-18px;letter-spacing:-12px}
  .em{position:absolute;right:90px;bottom:96px}
</style><div class="bg"><div class="tile"><div class="r">R</div><div class="em">${EMBLEM}</div></div></div>`)}`;
const SIZES = [[16,"icon_16x16.png"],[32,"icon_16x16@2x.png"],[32,"icon_32x32.png"],[64,"icon_32x32@2x.png"],[128,"icon_128x128.png"],[256,"icon_128x128@2x.png"],[256,"icon_256x256.png"],[512,"icon_256x256@2x.png"],[512,"icon_512x512.png"],[1024,"icon_512x512@2x.png"]];
app.whenReady().then(async () => {
  const win = new BrowserWindow({ width: 1024, height: 1024, x: -3000, y: -3000, frame: false, show: true });
  await win.loadURL(HTML); await new Promise((r) => setTimeout(r, 500));
  const img = await win.webContents.capturePage();
  if (img.isEmpty()) { console.error("captura vacía"); app.exit(1); return; }
  fs.mkdirSync(ICONSET, { recursive: true });
  for (const [s, n] of SIZES) fs.writeFileSync(path.join(ICONSET, n), img.resize({ width: s, height: s, quality: "best" }).toPNG());
  fs.writeFileSync(path.join(ASSETS, `icon-${V}.png`), img.resize({ width: 512, height: 512, quality: "best" }).toPNG());
  try { execFileSync("iconutil", ["-c", "icns", ICONSET, "-o", path.join(ASSETS, `icon-${V}.icns`)]); console.log(`icon-${V}.icns OK`); } catch (e) { console.error("iconutil:", e.message); }
  app.exit(0);
});
