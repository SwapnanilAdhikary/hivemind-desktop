import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("electronAPI", {
  showNotification: (title: string, body: string) =>
    ipcRenderer.invoke("show-notification", { title, body }),
  getBackendUrl: () => ipcRenderer.invoke("get-backend-url"),
});
