# 長者中心 CRM

一個為香港長者服務中心而設的客戶關係管理系統，用於管理會員、活動及暫託服務。

## 功能

### 儀表板
- KPI 概覽：活躍會員數、今日活動數、暫託批准人次、待處理申請數
- 本週暫託服務週曆，可點擊格子查看預約詳情及待處理申請，支援上下週導航
- 當日活動列表，可點擊查看詳情及報名名單，支援上下日導航

### 會員管理
- 新增、編輯、查看、刪除會員資料
- 記錄健康狀況、特殊需要、緊急聯絡人
- 搜尋及分頁瀏覽

### 活動管理
- 管理興趣班、健康講座、社交活動
- 會員報名及出席記錄
- 活動狀態追蹤（即將舉行、進行中、已完成、已取消）

### 暫託服務
- 月曆視圖，支援上下月導航
- 點擊時段格子查看已批准及待處理的會員名單
- 申請審批（待處理 → 已批准 / 已拒絕）
- 容量管理：4 個暫託位，全日佔用早上及下午名額

### 通知
- 追蹤逾 30 天未出席的非活躍會員
- 生成關懷訊息

## 技術架構

| 層級 | 技術 |
|------|------|
| 後端框架 | FastAPI |
| ORM | SQLAlchemy |
| 資料庫 | PostgreSQL |
| 模板引擎 | Jinja2 |
| CSS 框架 | Tailwind CSS + daisyUI |
| 動態互動 | HTMX |
| 伺服器 | Uvicorn |
| 套件管理 | uv |

## 本機開發

**前置需要：** Docker Desktop、Python 3.12+、uv

```bash
# 1. 複製專案
git clone https://github.com/bensonlsp/virtual_elderly_centre.git
cd virtual_elderly_centre

# 2. 複製環境變數設定
cp .env.example .env
# 編輯 .env 填入你的資料庫設定

# 3. 啟動 PostgreSQL（Docker）
docker run -d \
  --name eldercrm-postgres \
  -e POSTGRES_USER=eldercrm \
  -e POSTGRES_PASSWORD=eldercrm123 \
  -e POSTGRES_DB=eldercrm \
  -p 5432:5432 \
  postgres:16

# 4. 建立資料表
uv run python -c "from app.database import engine; from app.models import Base; Base.metadata.create_all(engine)"

# 5. 填入測試資料（可選）
uv run python scripts/seed_data.py

# 6. 啟動伺服器
uv run uvicorn app.main:app --reload
```

打開瀏覽器訪問 http://localhost:8000/dashboard

## 部署（Zeabur）

1. 將專案推上 GitHub
2. 在 Zeabur 建立專案，從 GitHub 匯入
3. 加入 PostgreSQL 服務，Zeabur 會自動注入 `POSTGRES_URI`
4. 在環境變數加入 `DATABASE_URL`（值為 PostgreSQL 的連線字串）
5. 部署完成後，在 Console 執行建立資料表指令：

```bash
uv run python -c "from app.database import engine; from app.models import Base; Base.metadata.create_all(engine)"
```

## 環境變數

| 變數 | 說明 |
|------|------|
| `DATABASE_URL` | PostgreSQL 連線字串 |
| `POSTGRES_URI` | Zeabur 自動注入（與 `DATABASE_URL` 二選一）|
| `CENTRE_NAME` | 中心名稱 |
| `CENTRE_PHONE` | 中心電話 |
| `CENTRE_ADDRESS` | 中心地址 |
