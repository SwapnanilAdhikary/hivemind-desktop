const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  showNotification: (title, body) =>
    ipcRenderer.invoke("show-notification", { title, body }),
  getBackendUrl: () => ipcRenderer.invoke("get-backend-url"),
});
