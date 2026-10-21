// Proceso principal de Electron: ventana, configuración persistente y notificaciones nativas.
import { app, BrowserWindow, ipcMain, Notification, shell } from 'electron'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

interface StoredConfig {
  apiUrl: string
}

// La URL del backend se guarda en %APPDATA%\AutoMarket\config.json; se puede cambiar desde
// Configuración (p. ej. a http://192.168.1.50:8000 en la LAN) sin recompilar la app.
const DEFAULT_API_URL = process.env.AUTOMARKET_API_URL ?? 'http://localhost:8000'
const configPath = (): string => join(app.getPath('userData'), 'config.json')

function readConfig(): StoredConfig {
  try {
    if (existsSync(configPath())) {
      const parsed = JSON.parse(readFileSync(configPath(), 'utf-8')) as Partial<StoredConfig>
      if (parsed.apiUrl) return { apiUrl: parsed.apiUrl }
    }
  } catch {
    // archivo dañado: se usan los valores por defecto
  }
  return { apiUrl: DEFAULT_API_URL }
}

function normalizeApiUrl(raw: unknown): string {
  const url = new URL(String(raw).trim())
  if (url.protocol !== 'http:' && url.protocol !== 'https:') throw new Error('La URL debe empezar con http:// o https://')
  return url.origin
}

function createWindow(): void {
  const win = new BrowserWindow({
    width: 1366,
    height: 860,
    minWidth: 1024,
    minHeight: 640,
    title: 'AutoMarket',
    backgroundColor: '#f4f6fa',
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  })

  win.once('ready-to-show', () => win.show())

  // Los enlaces externos se abren en el navegador, no dentro de la app
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) shell.openExternal(url)
    return { action: 'deny' }
  })

  if (process.env.ELECTRON_RENDERER_URL) {
    win.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    win.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

ipcMain.handle('config:get', () => ({ ...readConfig(), appVersion: app.getVersion() }))

ipcMain.handle('config:setApiUrl', (_event, raw: unknown) => {
  const apiUrl = normalizeApiUrl(raw)
  writeFileSync(configPath(), JSON.stringify({ ...readConfig(), apiUrl }, null, 2), 'utf-8')
  return { apiUrl, appVersion: app.getVersion() }
})

ipcMain.handle('notify', (_event, title: unknown, body: unknown) => {
  if (Notification.isSupported()) {
    new Notification({ title: String(title).slice(0, 80), body: String(body).slice(0, 200) }).show()
  }
})

app.setAppUserModelId('mx.automarket.desktop') // necesario para notificaciones en Windows

app.whenReady().then(() => {
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
