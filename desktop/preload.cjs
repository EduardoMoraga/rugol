// Rugol desktop — preload mínimo.
const { contextBridge, ipcRenderer, shell } = require("electron");
contextBridge.exposeInMainWorld("rugol", {
  platform: process.platform,
  openExternal: (url) => shell.openExternal(url),
  // Selector nativo de carpeta (para conectar una fuente de CVs a una búsqueda).
  pickFolder: () => ipcRenderer.invoke("rugol:pickFolder"),
});
