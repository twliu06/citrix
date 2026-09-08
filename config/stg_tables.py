"""
STG 層設定

來源是 RAW（raw_cda_prod 的 citrix schema），不再回頭連 Citrix。

⚠️ 為什麼 STG 用整表重建，而 RAW 不行
------------------------------------------------------------------
RAW 的來源 Citrix 只保留約 90 天，砍掉重建會永久失去歷史，所以 RAW 走
增量 upsert。STG 的來源是 RAW，完整歷史都在，隨時可以重算，
整表重建沒有任何資料遺失風險。

而且本表的 12 欄無法唯一識別一列 —— 來源 SQL 未選出
ApplicationInstance.Id，而多進程應用（例如 WorkFlow ERP GP 系統）
會在同一毫秒產生多筆 instance，投影成這 12 欄之後完全相同。
沒有 key 就做不了 upsert，整表重建是唯一可行的方式。
"""

TARGET_TABLE = "private.citrix_software_usage"

COLUMNS = [
    "user_identifier",
    "user_id",
    "app_name",
    "app_id",
    "session_key",
    "client_ip",
    "logon_started_at",
    "logon_ended_at",
    "session_started_at",
    "session_ended_at",
    "app_started_at",
    "app_ended_at",
]

# 對方（Power BI 報表維護者）提供並確認的取數邏輯，
# 原樣沿用，僅把來源從 Citrix 換成已落地的 RAW 表。
#
# 兩處與原版不同，均不影響語意：
#   1. WHERE e.LogOnStartDate > '{last_update_date}' 移除
#      —— 增量已在 RAW 層處理，STG 每次重算全量
#   2. 加上型別轉換（RAW 是 TEXT）：
#      user_id → BIGINT，app_id / session_key → UUID
SOURCE_SQL = """
SELECT
    d."UserName"::VARCHAR(20)   AS user_identifier,
    c."UserId"::BIGINT          AS user_id,
    b."Name"::VARCHAR(100)      AS app_name,
    a."ApplicationId"::UUID     AS app_id,
    a."SessionKey"::UUID        AS session_key,
    e."ClientAddress"           AS client_ip,
    e."LogOnStartDate"          AS logon_started_at,
    e."LogOnEndDate"            AS logon_ended_at,
    c."StartDate"               AS session_started_at,
    c."EndDate"                 AS session_ended_at,
    a."StartDate"               AS app_started_at,
    a."EndDate"                 AS app_ended_at
FROM citrix.application_launch a
    JOIN citrix.application  b ON a."ApplicationId" = b."Id"
    JOIN citrix.session      c ON a."SessionKey"    = c."SessionKey"
    JOIN citrix.user_account d ON c."UserId"        = d."Id"
    JOIN citrix.connection   e ON a."SessionKey"    = e."SessionKey"
ORDER BY a."StartDate"
"""
