# 資料庫遷移指南：DB 啟動方式統一 (KINA-331)

## 概述

自 2026-04-15 起，money_printer 改為與 KingArmy Trade Memory Engine 共用同一個 PostgreSQL instance，以實現統一的資料管理。

**主要變更：**
- 預設資料路徑：`~/.money_printer/pgdata` → `~/.kingarmy/db/`
- 預設埠號：`5432` → `54330`
- 環境變數支援：`DATA_DIR`、`EMBEDDED_PG_PORT`

---

## 情況 A：新使用者 或 無舊資料

**無需任何操作**。

啟動 money_printer 時會自動在 `~/.kingarmy/db/` 建立新的 PostgreSQL 實例（埠 54330）。

---

## 情況 B：已有舊資料在 `~/.money_printer/pgdata`

### 步驟 1：確認舊資料存在

```bash
ls -la ~/.money_printer/pgdata/PG_VERSION
```

如果檔案存在，說明有舊 PostgreSQL 資料。

### 步驟 2：選擇遷移方式

#### **方式 1：保留舊位置（推薦快速方式）**

透過環境變數繼續使用舊位置，避免資料遷移：

```bash
# .env 或 shell 環境設置
DATA_DIR=~/.money_printer/pgdata
EMBEDDED_PG_PORT=5432
```

這樣 money_printer 會沿用舊路徑啟動。但**不建議長期使用**，因為與記憶引擎使用的 `~/.kingarmy/db/` 不統一。

#### **方式 2：遷移到新位置（完整對齊）**

使用 PostgreSQL 工具進行資料遷移：

```bash
# 1. 備份舊資料（可選，但建議做）
mkdir -p ~/.backup
pg_dump -h localhost -p 5432 -U postgres -d money_printer > ~/.backup/money_printer.sql

# 2. 停止舊 PostgreSQL 實例（如果正在執行）
pg_ctl -D ~/.money_printer/pgdata stop

# 3. 初始化新位置
mkdir -p ~/.kingarmy/db

# 4. 移動資料目錄
mv ~/.money_printer/pgdata ~/.kingarmy/db/pgdata_backup
initdb -D ~/.kingarmy/db -U postgres

# 5. 還原資料
psql -h localhost -p 54330 -U postgres -f ~/.backup/money_printer.sql

# 6. 確認遷移成功
psql -h localhost -p 54330 -U postgres -d money_printer -c "\dt"
```

#### **方式 3：完全重新啟動（最簡單）**

如果舊資料不重要，可直接刪除：

```bash
rm -rf ~/.money_printer/pgdata
# money_printer 將自動在 ~/.kingarmy/db/ 建立新實例
```

---

## 環境變數參考

| 變數名 | 預設值 | 說明 |
|--------|--------|------|
| `DB_HOST` | 空 | 空 = 嵌入式模式；有值 = 外部 DB |
| `DB_PORT` | 54330 | 外部 DB 的埠號 |
| `DATA_DIR` | `~/.kingarmy/db` | 嵌入式 PG 資料目錄 |
| `EMBEDDED_PG_PORT` | 54330 | 嵌入式 PG 埠號 |

### 設定範例

```bash
# 使用新預設位置和埠
export DB_HOST=
export EMBEDDED_PG_PORT=54330
export DATA_DIR=~/.kingarmy/db

# 繼續用舊位置（臨時方案）
export DB_HOST=
export EMBEDDED_PG_PORT=5432
export DATA_DIR=~/.money_printer/pgdata
```

---

## 與記憶引擎的統一

money_printer 和 KingArmy Trade Memory Engine 現在共享同一個 PostgreSQL 實例：

```
~/.kingarmy/db/
├── PostgreSQL 實例 (port 54330)
    ├── money_printer database
    └── trade_memory database
```

兩個服務可同時執行，不會衝突（各自連接自己的 database）。

---

## 常見問題

### Q1：啟動時報錯 "Address already in use (port 5432/54330)"

**A:** 
- 舊 PostgreSQL 還在執行，停止它：
  ```bash
  pg_ctl -D ~/.money_printer/pgdata stop
  ```
- 或改用不同埠：
  ```bash
  export EMBEDDED_PG_PORT=5433
  ```

### Q2：能否讓 money_printer 和記憶引擎用不同的資料目錄？

**A:** 可以，但**不推薦**。使用 `DATA_DIR` 環境變數自訂路徑。但這樣會失去統一管理的好處。

### Q3：舊資料會丟失嗎？

**A:** 不會。舊資料仍在 `~/.money_printer/pgdata`。除非手動刪除，否則資料保留。

---

## 驗證遷移成功

啟動 money_printer 後，檢查：

```bash
# 1. 確認 PostgreSQL 在正確埠運行
psql -h localhost -p 54330 -U postgres -c "SELECT version();"

# 2. 確認 money_printer database 存在
psql -h localhost -p 54330 -U postgres -lqt | grep money_printer

# 3. 檢查資料表
psql -h localhost -p 54330 -U postgres -d money_printer -c "\dt"
```

---

## 相關 Issue

- **KINA-331**: 統一 DB 啟動方式 — 共用 ~/.kingarmy/db/ + port 54330
- **KINA-328**: money_printer 瘦身重構 EPIC

---

**更新時間**: 2026-04-15  
**版本**: 1.0
