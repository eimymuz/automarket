export interface AppConfig {
  apiUrl: string
  appVersion: string
}

declare global {
  interface Window {
    automarket: {
      getConfig: () => Promise<AppConfig>
      setApiUrl: (url: string) => Promise<AppConfig>
      notify: (title: string, body: string) => Promise<void>
    }
  }
}
