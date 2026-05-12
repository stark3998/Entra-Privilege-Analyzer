/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_CLIENT_ID: string;
  readonly VITE_API_BASE_URL: string;
  readonly VITE_LOCAL_MODE: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
