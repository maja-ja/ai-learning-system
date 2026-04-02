# Etymon Decoder — AI 英文字根學習平台

> 一個 18 歲自學生，獨立設計、開發、部署的全端 AI 教育工具。  
> 上線後首篇推廣貼文達 **2.5 萬次瀏覽、830 個讚**，目前持續成長中。  
> 永久免費開放：[etymon-decoder.com](https://etymon-decoder.com)

-----

## 這個專案是什麼

Etymon Decoder 是一個幫助學生用「字根拆解法」學英文的 AI 工具。輸入任何單字或主題，AI 會解析字根來源、拉丁文/希臘文脈絡、以及相關字族——讓記單字變成理解語言的過程。

針對台灣高中生設計，涵蓋學測常見字根，並提供知識庫瀏覽、小測驗、AI 生成講義等功能。

-----

## 我做了什麼

這是我一個人從零開始做的專案，包含：

- 產品方向與功能規劃（從 Streamlit 原型迭代到完整全端應用）
- 前端介面設計與開發（Vite + React + TypeScript）
- 後端 API 設計與開發（FastAPI + SQLite）
- AI 功能整合（Claude API、Gemini API，支援任務分級路由）
- 部署與維運（Cloudflare Tunnel、自訂網域）
- 內容行銷（Threads 帳號 @yasunaya_kad，單篇最高 2.5 萬瀏覽）

-----

## 技術架構

```
前端      Vite + React + TypeScript
後端      FastAPI (Python)
資料庫    SQLite（本地）/ Supabase（管理控制台）
AI        Anthropic Claude API / Google Gemini API
部署      Cloudflare Tunnel + 自訂網域
管理台    Next.js + Supabase + Clerk（獨立子專案）
```

-----

## 主要功能

|頁面      |功能                        |
|--------|--------------------------|
|字根學習    |39 個字根組、144 個字詞、圖鑑瀏覽、小測驗  |
|AI 解碼實驗室|輸入單字/主題，AI 生成字根解析與知識脈絡    |
|知識庫     |瀏覽筆記、今日隨機啟發、一鍵生成講義        |
|學測資料庫   |本地 Markdown 知識樹、全文搜尋、編輯   |
|講義排版    |AI 生成 + 模板，可匯出 A4 可列印 HTML|

-----

## 數據（截至 2026 年 4 月）

- Threads 帳號 30 天瀏覽：**3.4 萬次**
- 單篇最高互動：瀏覽 2.5 萬 / 讚 830 / 轉發 125
- 粉絲：275 人（自然成長，無付費推廣）

-----

## 關於我

**Kadus，18 歲，台中，自學生。**

沒有就讀大學。高中同等學力，學測備考中。

從 Gemini + Streamlit 的陽春原型，到現在有完整前後端、AI 整合、自訂網域的產品——這個專案是我過去一年學習的具體成果。

我習慣用「做東西」來學習，而不是只讀文件。

-----

## 連結

- 網站：[etymon-decoder.com](https://etymon-decoder.com)
- GitHub：[github.com/maja-ja/ai-learning-system](https://github.com/maja-ja/ai-learning-system)
- Threads：[@yasunaya_kad](https://www.threads.net/@yasunaya_kad)