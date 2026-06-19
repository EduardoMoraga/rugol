// Tipado del puente Electron expuesto por el preload (`window.rugol`).
// En el navegador puro no existe — por eso es opcional. Permite abrir URLs en
// el navegador externo del sistema en vez de dentro de la ventana Electron.
export {};

declare global {
  interface Window {
    rugol?: {
      openExternal?: (url: string) => void;
      // Selector NATIVO de carpeta del sistema (preload de Electron).
      // Devuelve la ruta elegida o null si el usuario cancela.
      pickFolder?: () => Promise<string | null>;
    };
  }
}
