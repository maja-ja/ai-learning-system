# 本機 SQLite 備份

本專案正式站目前使用 `backend/local.db` 作為主資料庫。建議在 Mac mini 上固定做備份，避免機器故障或誤刪時資料一起遺失。

## 手動備份

在專案根目錄執行：

```bash
python3 backend/backup_local_db.py
```

預設備份到：

```text
backend/backups/
```

檔名格式：

```text
local-YYYYMMDD-HHMMSS.db
```

預設只保留最近 `14` 份；可改為：

```bash
python3 backend/backup_local_db.py --keep 30
```

## 建議排程（macOS / LaunchAgent）

建立檔案：

```text
~/Library/LaunchAgents/com.etymon.backup-local-db.plist
```

內容如下，將 `/Users/cpr/ai-learning-system` 改成你的實際專案路徑：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.etymon.backup-local-db</string>

    <key>ProgramArguments</key>
    <array>
      <string>/usr/bin/python3</string>
      <string>/Users/cpr/ai-learning-system/backend/backup_local_db.py</string>
      <string>--keep</string>
      <string>30</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/cpr/ai-learning-system</string>

    <key>StartCalendarInterval</key>
    <dict>
      <key>Hour</key>
      <integer>3</integer>
      <key>Minute</key>
      <integer>15</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/tmp/etymon-backup.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/etymon-backup.err.log</string>
  </dict>
</plist>
```

載入：

```bash
launchctl unload ~/Library/LaunchAgents/com.etymon.backup-local-db.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.etymon.backup-local-db.plist
launchctl start com.etymon.backup-local-db
```

## 恢復方式

先停站，再將你要的備份覆蓋回主庫：

```bash
cp backend/backups/local-20260401-031500.db backend/local.db
```

然後重新啟動：

```bash
python3 serve_portable.py
```
