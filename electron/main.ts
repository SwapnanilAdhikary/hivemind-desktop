import { app, BrowserWindow, ipcMain, Notification } from "electron";
import path from "path";

let mainWindow: BrowserWindow | null = null;

const isDev = process.env.NODE_ENV !== "production" || !app.isPackaged;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    title: "Agent Platform",
    backgroundColor: "#0f172a",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    mainWindow.loadURL("http://localhost:5173");
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

// IPC: Show native OS notification
ipcMain.handle("show-notification", (_event, { title, body }: { title: string; body: string }) => {
  new Notification({ title, body }).show();
});

// IPC: Get backend URL
ipcMain.handle("get-backend-url", () => {
  return "http://127.0.0.1:8000";
});
