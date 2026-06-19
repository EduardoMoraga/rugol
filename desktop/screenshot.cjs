const { app, BrowserWindow } = require("electron");
const fs = require("node:fs");
app.disableHardwareAcceleration();
const URL = process.argv.find(a => a && a.startsWith("http"));
const OUT = process.argv.find(a => a && a.endsWith(".png")) || "/tmp/shot.png";
app.whenReady().then(async () => {
  const win = new BrowserWindow({ width: 1480, height: 920, x: -4000, y: -4000, show: true, webPreferences: { offscreen: false } });
  await win.loadURL(URL); await new Promise(r => setTimeout(r, 4500));
  fs.writeFileSync(OUT, (await win.webContents.capturePage()).toPNG());
  console.log("shot OK"); app.exit(0);
});
