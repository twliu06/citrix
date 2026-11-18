"""
STG 層設定

來源是 RAW（raw_cda_prod 的 citrix schema），不再回頭連 Citrix。
三個站台各自一張 STG 表，由該站台的五張 RAW 表 JOIN 而成，
站台清單見 config/raw_tables.py 的 CITRIX_SITES。

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

from config.raw_tables import CITRIX_SITES

# 站台前綴 → STG 表
TARGET_TABLES = {
    site: f"private.citrix_{site}_usage"
    for site in CITRIX_SITES
}

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
# 原樣沿用，僅把來源從 Citrix 換成已落地的 RAW 表，三個站台共用。
#
# 兩處與原版不同，均不影響語意：
#   1. WHERE e.LogOnStartDate > '{last_update_date}' 移除
#      —— 增量已在 RAW 層處理，STG 每次重算全量
#   2. 加上型別轉換（RAW 是 TEXT）：
#      user_id → BIGINT，app_id / session_key → UUID，
#      時間欄位 → TIMESTAMP(6)（RAW 已是台北時間的字串，不需再換時區）
#
# ⚠️ 以應用程式啟動紀錄為主體 JOIN，只有啟動過應用程式的工作階段才會出現。
#    行政系統站台的「行動辦公室」發佈的是整個桌面，不是應用程式，
#    這類桌面工作階段若沒有應用程式啟動紀錄，就不會出現在 STG，
#    要查請直接讀 RAW 的 session 與 connection。
#
# {site} 由 build_source_sql() 代入站台前綴。
SOURCE_SQL_TEMPLATE = """
SELECT
    d."UserName"::VARCHAR(20)   AS user_identifier,
    c."UserId"::BIGINT          AS user_id,
    b."Name"::VARCHAR(100)      AS app_name,
    a."ApplicationId"::UUID     AS app_id,
    a."SessionKey"::UUID        AS session_key,
    e."ClientAddress"                   AS client_ip,
    e."LogOnStartDate"::TIMESTAMP(6)    AS logon_started_at,
    e."LogOnEndDate"::TIMESTAMP(6)      AS logon_ended_at,
    c."StartDate"::TIMESTAMP(6)         AS session_started_at,
    c."EndDate"::TIMESTAMP(6)           AS session_ended_at,
    a."StartDate"::TIMESTAMP(6)         AS app_started_at,
    a."EndDate"::TIMESTAMP(6)           AS app_ended_at
FROM citrix.{site}_application_launch a
    JOIN citrix.{site}_application  b ON a."ApplicationId" = b."Id"
    JOIN citrix.{site}_session      c ON a."SessionKey"    = c."SessionKey"
    JOIN citrix.{site}_user_account d ON c."UserId"        = d."Id"
    JOIN citrix.{site}_connection   e ON a."SessionKey"    = e."SessionKey"
ORDER BY a."StartDate"::TIMESTAMP(6)
"""


def build_source_sql(site: str) -> str:
    return SOURCE_SQL_TEMPLATE.format(site=site)
