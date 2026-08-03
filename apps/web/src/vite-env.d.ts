/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_AUTH_ENABLED?: string;
  readonly VITE_AUTH_PROVIDER?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
