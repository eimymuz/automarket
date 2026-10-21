// Puente seguro entre Electron y React: solo se expone lo estrictamente necesario.
import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('automarket', {
  getConfig: () => ipcRenderer.invoke('config:get'),
  setApiUrl: (url: string) => ipcRenderer.invoke('config:setApiUrl', url),
  notify: (title: string, body: string) => ipcRenderer.invoke('notify', title, body)
})
