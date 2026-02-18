/// <reference types="vite/client" />

interface ElectronAPI {
  showNotification: (title: string, body: string) => Promise<void>;
  getBackendUrl: () => Promise<string>;
}

interface Window {
  electronAPI?: ElectronAPI;
}
