# 🚀 AI 學習系統 - 現代化架構遷移方案 v3.0

## 📋 架構概覽

### 技術棧選定

```
前端層          Next.js 14 (App Router)
                ├─ React 18
                ├─ TypeScript
                ├─ TailwindCSS
                └─ SWR / TanStack Query

API 層           FastAPI 0.104+
                ├─ Pydantic V2
                ├─ SQLAlchemy ORM
                └─ Async/Await

快取層           Redis 7.0+
                ├─ Session 管理
                ├─ 實時消息隊列
                └─ LLM 回應緩存

數據層           PostgreSQL 15+
                ├─ 主業務數據
                ├─ pgvector 向量存儲
                └─ 全文搜索 (GIN 索引)

AI 服務          OpenAI API
                ├─ GPT-4 / GPT-4o (文本)
                ├─ Embedding (向量化)
                └─ Vision (圖像分析)

部署             Docker + Docker Compose
                ├─ 本地開發
                ├─ VPS 佈署
                └─ CI/CD 流程
```

## 📁 項目目錄結構

```
ai-learning-system-v3/
│
├── backend/                          # FastAPI 後端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI 應用實例
│   │   ├── config.py                # 環境配置
│   │   ├── dependencies.py          # 依賴注入
│   │   │
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── endpoints/
│   │   │   │   │   ├── auth.py     # 認證
│   │   │   │   │   ├── etymon.py   # 單詞解碼
│   │   │   │   │   ├── handout.py  # 講義生成
│   │   │   │   │   └── search.py   # 向量搜索
│   │   │   │   └── router.py
│   │   │
│   │   ├── core/
│   │   │   ├── security.py          # JWT、CORS 等
│   │   │   ├── ai_service.py        # OpenAI 集成
│   │   │   └── vector_store.py      # pgvector 操作
│   │   │
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── session.py           # 數據庫會話
│   │   │   └── models.py            # SQLAlchemy 模型
│   │   │
│   │   ├── schemas/
│   │   │   ├── etymon.py
│   │   │   ├── handout.py
│   │   │   └── user.py
│   │   │
│   │   ├── services/
│   │   │   ├── etymon_service.py
│   │   │   ├── handout_service.py
│   │   │   ├── cache_service.py     # Redis 操作
│   │   │   └── ai_service.py
│   │   │
│   │   └── utils/
│   │       ├── logger.py
│   │       ├── validators.py
│   │       └── helpers.py
│   │
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_etymon.py
│   │   └── test_handout.py
│   │
│   ├── migrations/                  # Alembic 數據庫遷移
│   │   ├── versions/
│   │   └── env.py
│   │
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── main.py                      # 啟動腳本
│
├── frontend/                        # Next.js 前端
│   ├── app/
│   │   ├── layout.tsx               # 根布局
│   │   ├── page.tsx                 # 首頁
│   │   │
│   │   ├── (auth)/
│   │   │   ├── login/
│   │   │   │   └── page.tsx
│   │   │   └── register/
│   │   │       └── page.tsx
│   │   │
│   │   ├── (dashboard)/
│   │   │   ├── etymon/
│   │   │   │   ├── page.tsx         # 單詞解碼首頁
│   │   │   │   ├── [id]/
│   │   │   │   │   └── page.tsx     # 詳情
│   │   │   │   └── lab/
│   │   │   │       └── page.tsx     # 實驗室
│   │   │   │
│   │   │   ├── handout/
│   │   │   │   ├── page.tsx         # 講義首頁
│   │   │   │   ├── create/
│   │   │   │   │   └── page.tsx
│   │   │   │   └── batch/
│   │   │   │       └── page.tsx
│   │   │   │
│   │   │   └── dashboard/
│   │   │       └── page.tsx
│   │   │
│   │   ├── api/
│   │   │   ├── auth/route.ts        # 後端代理
│   │   │   ├── etymon/route.ts
│   │   │   └── handout/route.ts
│   │   │
│   │   └── error.tsx / loading.tsx
│   │
│   ├── components/
│   │   ├── layouts/
│   │   │   ├── MainLayout.tsx
│   │   │   └── DashboardLayout.tsx
│   │   │
│   │   ├── etymon/
│   │   │   ├── EtymonCard.tsx
│   │   │   ├── EtymonSearch.tsx
│   │   │   ├── LabInterface.tsx
│   │   │   └── SearchResults.tsx
│   │   │
│   │   ├── handout/
│   │   │   ├── SingleHandout.tsx
│   │   │   ├── BatchProcessor.tsx
│   │   │   ├── HandoutPreview.tsx
│   │   │   ├── TemplateSelector.tsx
│   │   │   └── HistoryPanel.tsx
│   │   │
│   │   ├── common/
│   │   │   ├── NavBar.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Toast.tsx
│   │   │   └── LoadingSpinner.tsx
│   │   │
│   │   └── ui/
│   │       ├── Button.tsx
│   │       ├── Input.tsx
│   │       ├── Modal.tsx
│   │       └── Tabs.tsx
│   │
│   ├── lib/
│   │   ├── api.ts                   # API 客戶端
│   │   ├── hooks.ts                 # 自定義 Hook
│   │   ├── auth.ts                  # 認證邏輯
│   │   └── utils.ts
│   │
│   ├── styles/
│   │   └── globals.css
│   │
│   ├── public/
│   │   └── images/
│   │
│   ├── .env.local.example
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── package.json
│   └── README.md
│
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   ├── docker-compose.yml           # 完整開發環境
│   └── docker-compose.prod.yml      # 生產配置
│
├── docs/
│   ├── API.md                       # API 文檔
│   ├── ARCHITECTURE.md              # 架構文檔
│   ├── DEPLOYMENT.md                # 部署指南
│   ├── DATABASE.md                  # 數據庫設計
│   └── MIGRATION.md                 # 遷移指南
│
├── .github/
│   └── workflows/
│       ├── ci.yml                   # 自動化測試
│       ├── deploy.yml               # 自動部署
│       └── lint.yml                 # 代碼檢查
│
├── scripts/
│   ├── setup.sh                     # 初始化腳本
│   ├── migrate.py                   # 數據遷移腳本
│   └── dev.sh                       # 開發環境啟動
│
├── .env.example
├── .gitignore
├── README.md
└── ARCHITECTURE.md
```

## 🔄 系統架構圖

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户浏览器                                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTPS
                    ┌──────────▼──────────┐
                    │   Next.js 前端       │
                    │  (Server Components) │
                    │   - 頁面渲染         │
                    │   - SSR/SSG          │
                    │   - 客户端互動       │
                    └──────────┬───────────┘
                               │ JSON/gRPC
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
    ┌───▼──────────┐   ┌──────▼────────┐   ┌────────▼────┐
    │   FastAPI    │   │  Redis 快取   │   │  WebSocket  │
    │   - REST API │   │  - Sessions   │   │   - 實時    │
    │   - GraphQL  │   │  - 消息隊列   │   │     通知    │
    ├──────────────┤   └───────────────┘   └─────────────┘
    │ 核心服務:    │
    │ - 認證       │
    │ - Etymology  │
    │ - Handout    │
    │ - AI 服務    │
    └───┬──────────┘
        │
    ┌───▼──────────────────────────────────┐
    │      PostgreSQL + pgvector           │
    │  ┌────────────────────────────────┐  │
    │  │ 業務數據表                       │  │
    │  │ - users, etymons               │  │
    │  │ - handouts, templates           │  │
    │  ├────────────────────────────────┤  │
    │  │ 向量表                          │  │
    │  │ - etymon_embeddings (1536 dims)│  │
    │  │ - handout_embeddings           │  │
    │  │ - (Pgvector 索引優化查詢)      │  │
    │  └────────────────────────────────┘  │
    └────────────────────────────────────┘
        │
    ┌───▼──────────────────────┐
    │   外部 API 服務           │
    ├──────────────────────────┤
    │ OpenAI API               │
    │ - GPT-4o (文本生成)      │
    │ - text-embedding-3 (向量)│
    │ - Vision (圖像分析)      │
    └──────────────────────────┘
```

## 🔐 安全架構

```
┌─────────────────────────────────────────────────┐
│           SSL/TLS 加密通道                       │
├─────────────────────────────────────────────────┤
│  CORS 政策 (跨域資源)                           │
├─────────────────────────────────────────────────┤
│  JWT Token 認證                                  │
│  - Access Token (15 分鐘)                       │
│  - Refresh Token (7 天)                         │
├─────────────────────────────────────────────────┤
│  Role-Based Access Control (RBAC)              │
│  - 普通用戶                                      │
│  - 高級用戶                                      │
│  - 管理員                                        │
├─────────────────────────────────────────────────┤
│  API Rate Limiting (Redis)                      │
│  - 100 req/分鐘 (未認證)                        │
│  - 1000 req/分鐘 (認證)                         │
├─────────────────────────────────────────────────┤
│  環境變數管理                                     │
│  - API Key 加密存儲                             │
│  - 不提交敏感信息到 Git                         │
└─────────────────────────────────────────────────┘
```

## 🔌 API 設計概覽

### 認證端點
```
POST   /api/v1/auth/register      # 用戶註冊
POST   /api/v1/auth/login         # 登錄
POST   /api/v1/auth/refresh       # 刷新 Token
POST   /api/v1/auth/logout        # 登出
```

### Etymology Lab API
```
GET    /api/v1/etymon/            # 列表（分頁）
GET    /api/v1/etymon/{id}        # 詳情
POST   /api/v1/etymon/search      # 向量搜索
POST   /api/v1/etymon/batch       # 批量解碼
POST   /api/v1/etymon/generate    # AI 生成
```

### Handout API
```
GET    /api/v1/handout/           # 列表
POST   /api/v1/handout/           # 創建
GET    /api/v1/handout/{id}       # 詳情
PUT    /api/v1/handout/{id}       # 更新
DELETE /api/v1/handout/{id}       # 刪除
POST   /api/v1/handout/{id}/pdf   # 生成 PDF
POST   /api/v1/handout/batch      # 批量生成
```

### 搜索 API
```
POST   /api/v1/search/hybrid      # 混合搜索 (文本 + 向量)
POST   /api/v1/search/vector      # 純向量搜索
POST   /api/v1/search/full-text   # 全文搜索
```

## 📊 數據庫設計（核心表）

### Users 表
```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255),
    username VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_admin BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Etymons 表
```sql
CREATE TABLE etymons (
    id BIGSERIAL PRIMARY KEY,
    word VARCHAR(255) UNIQUE NOT NULL,
    category VARCHAR(100),
    definition TEXT,
    roots TEXT,
    breakdown TEXT,
    meaning TEXT,
    native_vibe TEXT,
    example TEXT,
    synonym_nuance TEXT,
    usage_warning TEXT,
    memory_hook TEXT,
    phonetic VARCHAR(255),
    embedding vector(1536),  -- OpenAI text-embedding-3-small
    created_by BIGINT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_etymons_word ON etymons USING GIN(to_tsvector('chinese', word));
CREATE INDEX idx_etymons_embedding ON etymons USING IVFFlat(embedding vector_cosine_ops);
```

### Handouts 表
```sql
CREATE TABLE handouts (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    template_name VARCHAR(100),
    style VARCHAR(100),
    user_id BIGINT REFERENCES users(id),
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_public BOOLEAN DEFAULT false
);
```

## 🧠 核心服務架構

### 1. AI 服務 (OpenAI Integration)
- 文本生成 (講義、解釋)
- 向量化 (Embeddings)
- 圖像分析 (PDFs, 照片)
- 成本優化 (緩存、批量)

### 2. 向量搜索
- pgvector IVFFlat 索引
- 相似度計算 (cosine distance)
- 混合搜索 (文本 + 向量)

### 3. 快取策略 (Redis)
- Session: TTL 1 小時
- API 響應: TTL 24 小時
- LLM 回應: TTL 7 天
- 消息隊列: 待消費

### 4. 認證系統
- JWT (HS256)
- OAuth2 (可選 Google/GitHub)
- 權限控制 (RBAC)

## 📈 開發進度跟踪

| 階段 | 任務 | 優先級 | 狀態 |
|------|------|--------|------|
| 1 | 後端架構搭建 | 🔴 高 | ⏳ |
| 2 | 前端基礎框架 | 🔴 高 | ⏳ |
| 3 | 數據庫設計遷移 | 🔴 高 | ⏳ |
| 4 | OpenAI 集成 | 🔴 高 | ⏳ |
| 5 | 特性實現 | 🟡 中 | ⏳ |
| 6 | 測試和優化 | 🟡 中 | ⏳ |
| 7 | Docker 部署 | 🟡 中 | ⏳ |
| 8 | 上線和監控 | 🟢 低 | ⏳ |

## 🔄 遷移計劃

### 階段 1: 基礎設施 (1-2 週)
- ✅ 創建 FastAPI 項目
- ✅ 配置 PostgreSQL + Redis
- ✅ 搭建 Next.js 項目
- ✅ 設置 CI/CD

### 階段 2: 核心 API (2-3 週)
- ✅ 認證系統
- ✅ Etymology CRUD
- ✅ Handout CRUD
- ✅ OpenAI 集成

### 階段 3: 前端實現 (2-3 週)
- ✅ 頁面組件
- ✅ 表單和驗證
- ✅ 搜索和過濾
- ✅ 實時更新

### 階段 4: 數據遷移 (1 週)
- ✅ SQLite → PostgreSQL 遷移腳本
- ✅ 向量化現有數據
- ✅ 數據驗證
- ✅ 備份

### 階段 5: 部署和優化 (1 週)
- ✅ Docker 配置
- ✅ 性能測試
- ✅ 安全審計
- ✅ 上線

## 🎯 成功指標

- API 響應時間 < 200ms (95th percentile)
- 向量搜索延遲 < 500ms
- 可用性 > 99.5%
- 測試覆蓋率 > 80%
- 成本優化 (OpenAI token 使用)

---

**開始日期**: 2026-03-11  
**預計完成**: 2026-04-22  
**狀態**: 規劃中  
**負責人**: AI 開發團隊
