# citrix 雲端軟體使用紀錄管線

把 Citrix Virtual Apps 的應用程式使用紀錄，從監控資料庫抽進 Postgres，供 Power BI 報表「Citrix 雲端軟體」使用。

## 🔄 資料流

```
CitrixFCU02Monitoring (SQL Server, 140.134.136.28)
        │  五張基底表，增量 upsert（依 ModifiedDate）
        ▼
raw_cda_prod / schema citrix
        │  五表 JOIN，型別轉換
        ▼
stg_cda_prod / schema private
        │
        ▼
Power BI「Citrix 雲端軟體」
```

## ⚠️ 這個專案最重要的一件事：來源只保留 90 天

Citrix 監控資料庫會自動清除過期資料，實測各粒度的保留期：

| 資料層 | 保留 |
|---|---|
| 明細（Session、Connection、ApplicationInstance） | 約 90 天 |
| 日彙總 `Granularity=1440` | 約 90 天 |
| 時彙總 `Granularity=60` | 約 32 天 |
| 分鐘彙總 `Granularity=1`、ResourceUtilization | 3～4 天 |

**RAW 層是這份資料唯一的長期保存處。** 排程停跑超過 90 天，中間那段就永久消失，無法回補。這與 fcu_db、researchgo 不同 —— 那些來源本身留有完整歷史，漏跑幾天補跑即可。

因此 RAW **不能**用 truncate 整表重建，只能走增量。

## 📡 來源

`CitrixFCU02Monitoring` 的 `MonitorData` schema 共 72 張表，本專案只用其中 5 張：

| 來源表 | RAW 表 | 欄位 | 自然鍵 |
|---|---|---|---|
| `MonitorData.Application` | `citrix.application` | 11 | `Id` |
| `MonitorData.ApplicationInstance` | `citrix.application_launch` | 7 | `Id` |
| `MonitorData.Session` | `citrix.session` | 18 | `SessionKey` |
| `MonitorData.User` | `citrix.user_account` | 8 | `Id` |
| `MonitorData.Connection` | `citrix.connection` | 37 | `Id` |

### ⚠️ 來源是 UTC，倉儲一律存台北時間

Citrix 資料庫的時間欄位全部是 UTC，而且沒有任何欄位標記時區。把 Session 起始時間按小時分組就看得出來：直接讀 DB 的值，高峰落在清晨 5–6 點、離峰在晚上 8–11 點；**+8 之後**才是合理的校園作息（下午 1–3 點主峰、晚上 8–10 點次峰、凌晨 2–7 點近乎歸零）。

**倉儲內禁止儲存 UTC。** 來源的時間欄位在寫入 RAW 之前就會轉成 `Asia/Taipei`，轉換一律走 `utils/time_utils.py` 的 `utc_to_taipei()`。STG 的來源是 RAW，直接繼承台北時間，不再另外轉換。

這樣做是為了避免同一列裡混著兩種時區 —— `created_at`／`updated_at` 是 `now_taipei()` 產生的台北時間，若來源欄位保持 UTC，同一筆資料的 `app_started_at` 會比 `created_at` 早 8 小時，下游拿去比對必然出錯。

> ⚠️ **連帶影響：水位線送回來源前要轉回 UTC。**
> RAW 存的是台北時間，`MAX("ModifiedDate")` 讀出來自然也是台北時間；但 Citrix 來源是 UTC，直接拿去查等於用「未來 8 小時」的條件過濾，**會回傳 0 筆而讓管線靜默停擺**。`utils/incremental_etl.py` 用 `taipei_to_utc()` 處理這一步，改動增量邏輯時不要動掉它。

### ⚠️ 資料列會就地更新

Session 開始時先寫入一列，結束時才回填 `EndDate`、`ExitCode`，同時 `ModifiedDate` 往後跳。所以增量水位線必須用 `ModifiedDate`，不能用 `CreatedDate` 或 `StartDate` —— 否則那些後續更新永遠抓不到。

### ⚠️ 這個站台只涵蓋部分軟體

FCU02 只發佈 31 個應用，以統計／工程軟體為主（SPSS、SAS、MATLAB、Minitab、Multisim、Stata、LabVIEW）。

Power BI 報表上的 ACL、ANSYS、ArcGIS、Archicad、Autodesk、Creo Parametric、ETABS、校務系統、櫃台服務系統**都不在這個站台**。報表的 `concurrent_snapshot` 有 `DB` 欄位，值為 `FCU01`、`FCU02`、`FCUVDI` —— 另外兩個站台的連線資訊尚未取得。

## 🗄️ 資料表

### raw：`raw_cda_prod` / schema `citrix`

欄位名稱**完全照抄來源基底表**（SQL Server 駝峰式），PostgreSQL 需以雙引號查詢：

```sql
SELECT "SessionKey", "StartDate" FROM citrix.session;
```

型態只有兩種：**時間欄位 `TIMESTAMP(6)`（已轉台北時間），其餘一律 `TEXT`**。除 `id`、`created_at`、`updated_at` 三個系統欄位外皆可為空 —— RAW 的職責是收得進來，不是擋資料。

| 表 | 說明 | 筆數 |
|---|---|---|
| `citrix.application` | 應用程式清單 | 41 |
| `citrix.application_launch` | 應用程式啟動紀錄 | ~2,600 |
| `citrix.session` | 工作階段紀錄 | ~2,100 |
| `citrix.user_account` | 使用者清單 | ~14,300 |
| `citrix.connection` | 連線紀錄 | ~2,300 |

`citrix.connection` 的 21 個時間欄位是登入流程的完整拆解：`BrokeringDate` → `VMStartStartDate/EndDate` → `HdxStartDate/EndDate` → `GpoStartDate/EndDate` → `LogOnScriptsStartDate/EndDate` → `ProfileLoadStartDate/EndDate` → `InteractiveStartDate/EndDate`。要做「登入為什麼慢」的分析不必再抽一次。

### stg：`stg_cda_prod` / schema `private`

`private.citrix_software_usage` —— 五表 JOIN 後的使用明細，12 個業務欄位。

**資料分級：第二級（高度敏感）。** 依《逢甲大學校務資料申請及使用作業要點》第三條第二款，一般個人資料無論是否去識別化，可直接或間接識別個人身分者屬第二級，要點明文列舉「學號」。本表 `user_identifier` 存學號／職員證號。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `user_identifier` | `VARCHAR(20)` | 使用者證號 |
| `user_id` | `BIGINT` | 使用者識別碼 |
| `app_name` | `VARCHAR(100)` | 軟體名稱（不含版本後綴） |
| `app_id` | `UUID` | 軟體識別碼 |
| `session_key` | `UUID` | 工作階段識別碼 |
| `client_ip` | `VARCHAR(50)` | 用戶端 IP |
| `logon_started_at` / `logon_ended_at` | `TIMESTAMP(6)` | 登入起訖 |
| `session_started_at` / `session_ended_at` | `TIMESTAMP(6)` | 工作階段起訖 |
| `app_started_at` / `app_ended_at` | `TIMESTAMP(6)` | 軟體使用起訖 |

## ⚠️ STG 沒有唯一鍵，也不做去重

取數 SQL 由 Power BI 報表維護者提供並確認，本專案原樣沿用。有兩個後果要知道：

**一、Session 與 Connection 是 1:N。** 使用者斷線重連會產生多筆 Connection，JOIN 未去重，同一次應用啟動會依連線數重複多列。實測 2,574 筆應用啟動會展開成 3,176 列（1.23 倍）。**「使用次數」與「使用總時間」因此會高估約 23%。** 這是來源端確認過的既有行為，維持不變。

**二、12 個欄位無法唯一識別一列。** 取數 SQL 未選出 `ApplicationInstance.Id`，而多進程應用（例如 WorkFlow ERP GP 系統）會在同一毫秒產生多筆 instance —— 實測某個 session 有 12 筆 `application_launch`，其中 4 筆的 12 欄完全相同。

因此 STG 改用整表重建，不做 key 比對。RAW 保有完整歷史，STG 隨時可以重算，重建不會造成資料遺失。

## 🚀 使用方式

### 安裝

```bash
docker compose up -d --build
```

Dockerfile 內含 Microsoft ODBC Driver 18 for SQL Server，build 時會驗證驅動程式註冊成功。base image 釘住 `python:3.11-slim-bookworm` —— 套件庫路徑綁 Debian 版本，不可改用浮動的 tag。

### 建 schema 與資料表（只需執行一次）

```sql
CREATE SCHEMA IF NOT EXISTS citrix;
COMMENT ON SCHEMA citrix IS 'Citrix 雲端軟體服務（應用程式、工作階段、連線、使用者）';
```

```bash
docker exec citrix_etl python -m raw.application.create_table
docker exec citrix_etl python -m raw.application_launch.create_table
docker exec citrix_etl python -m raw.session.create_table
docker exec citrix_etl python -m raw.user_account.create_table
docker exec citrix_etl python -m raw.connection.create_table
docker exec citrix_etl python -m stg.create_table
```

### 同步資料

```bash
docker exec citrix_etl python -m raw.main all          # 五張表
docker exec citrix_etl python -m raw.main session      # 指定表
docker exec citrix_etl python -m stg.main
```

## 📁 專案結構

```
citrix/
├── config/
│   ├── raw_tables.py       五張來源表設定（含 incremental_key、key_cols）
│   └── stg_tables.py       STG 目標表與取數 SQL
├── raw/
│   ├── main.py             共用驅動，所有表共用一支
│   ├── application/
│   ├── application_launch/
│   ├── session/
│   ├── user_account/
│   └── connection/         各一支 create_table.py
├── stg/
│   ├── main.py
│   └── create_table.py
├── utils/
│   ├── db_citrix.py        來源 SQL Server
│   ├── db_raw.py           目標 Postgres（raw）
│   ├── db_stg.py           目標 Postgres（stg）
│   ├── incremental_etl.py  RAW 增量 upsert
│   ├── logger.py
│   └── time_utils.py
└── deploy/cron.d/citrix    排程
```

## ⏱️ 排程

```
30 2 * * *  每天 02:30（台北時間）
```

安裝：

```bash
sudo mkdir -p /var/log/citrix && sudo chown twliu:twliu /var/log/citrix
sudo cp deploy/cron.d/citrix /etc/cron.d/citrix
```

> ⚠️ `/etc/cron.d/citrix` 權限必須是 644、擁有者 root，否則 cron 會整份忽略且不報錯。檔名也不能含 `.` 等特殊字元。

排在 02:30 的理由：避開日間使用尖峰（台北時間 13–15 時為主峰），且距離 Power BI 語意模型的更新時間（約中午 12:30）有足夠緩衝。

`raw` 與 `stg` 用 `&&` 串接 —— raw 失敗就不跑 stg，避免拿半套的來源資料去覆蓋已經正確的 stg。實測一輪約 10 秒。

### RAW 用 upsert，STG 用整表重建

RAW 每次抓回「水位線往回退 30 天」的資料，依自然鍵比對：新的 INSERT、有變的 UPDATE、**沒變的完全不寫入**（被 `WHERE ... IS DISTINCT FROM` 擋下）。因此 `id` 保持穩定，`updated_at` 的語意是「內容最後變動的時間」。

回溯視窗而非嚴格的 `> 水位線`，是為了收到那些在水位線通過後才被更新的列。視窗內既有的資料不會被刪除，只是重新比對一次，所以拉長視窗不會有資料遺失風險，代價只是多比對幾筆。`MAX_LOOKBACK_DAYS = 60` 是避免無意義的大範圍掃描。

STG 的來源是 RAW，完整歷史都在，整表重建沒有風險。

### ⚠️ flock 靜默跳過

`flock -n` 拿不到鎖就立刻放棄且不留痕跡，可能連續數天沒跑而無人察覺。這個專案對此特別敏感（見上方 90 天保留期），建議定期確認水位線有在推進：

```sql
SELECT MAX("ModifiedDate") FROM citrix.session;
```

## 🐛 來源資料已知問題

- **`Connection.ConnectedViaHostName` 全無有效值** —— 559 筆 NULL 加 2,160 筆 `"Unresolved"`，無法用來分析經由哪台 Gateway 進來。
- **`Connection` 的用戶端資訊有 17.8% 為空**，幾乎完全對應 `ConnectionFailureLog` 的筆數 —— 用戶端資訊為空代表連線根本沒建立成功。
- **`Session.SessionIdleTime` 型別是 `datetime` 但語意是閒置時長**，值長得像 `2026-09-04 07:52:06`。來源設計如此，怎麼解讀留給下游。
- **`Application` 表同一個應用會有多筆**（新舊版本、啟用／停用並存），例如 SPSS 有 18/21/22/23/24 五筆。聚合要用 `Name` 或 `PublishedName`，不要用 `Id`。
- **`Name` 與 `PublishedName` 有 5 個應用不同**，差在版本後綴（`Access` / `Access 2024`）。取數 SQL 用的是 `Name`。
- **失敗代碼沒有對照表** —— `ConnectionFailureCategory` 只有數字沒有名稱欄位。約 20% 的 session 非正常結束（`ExitCode` 4/7/21），要做故障分析需先向 Citrix 官方文件確認代碼語意。

