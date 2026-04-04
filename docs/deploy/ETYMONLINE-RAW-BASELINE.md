# Etymonline 原始資料基底（CSV）

目標：先抓網站、先存原始資料，未來所有單字生成都以這份資料為基底。

## 1) 抓取腳本

路徑：`scripts/fetch_etymonline_raw.py`

### 基本用法

```bash
python3 scripts/fetch_etymonline_raw.py --word hello
python3 scripts/fetch_etymonline_raw.py --words-file words.txt
```

### 建議用法（增量）

```bash
python3 scripts/fetch_etymonline_raw.py \
  --words-file words.txt \
  --out data/etymonline_raw.csv \
  --append \
  --delay-ms 600
```

## 2) 輸出欄位（原始基底）

- `word`: 單字（硬查找 key）
- `url`: 來源頁 URL
- `status`: `ok` / `not_found` / `http_error` / `parse_empty` / `error`
- `http_status`: HTTP 狀態碼（若未知為 0）
- `fetched_at`: 抓取時間（UTC ISO）
- `title`: 網頁標題
- `origin_and_history`: 文字區塊抽取
- `entries_linking_to`: 關聯詞區塊抽取
- `raw_text`: 去標籤後純文字（截斷上限 50,000 字）
- `raw_html_excerpt`: 原始 HTML 前段（截斷上限 5,000 字）
- `error`: 錯誤訊息

## 3) 安全與流程原則

- 查詢模式只接受 `word`（硬查找），不接受自由提示詞。
- 若 `word` 沒命中資料庫，回傳 `not_found`，不要改走自由生成。
- 前端風格只能按鈕枚舉；後端僅接受白名單 `style enum`。
- 生成時只能引用本 CSV（或其入庫版本）內容作為解釋基底。
