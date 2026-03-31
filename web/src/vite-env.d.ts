/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 正式環境 FastAPI 根網址，勿結尾斜線。例：https://api.etymon-decoder.com */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
