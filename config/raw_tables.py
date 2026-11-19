"""
RAW 層來源表設定

來源：三個 Citrix 站台的監控資料庫（SQL Server）的 MonitorData schema。
三個站台的表結構相同，各自一組 RAW 表，以表名前綴區分站台。

⚠️ 為什麼三個站台不放進同一組表
------------------------------------------------------------------
各站台的識別碼（User.Id、Connection.Id 等）是各自編的流水號，
同一個 Id 在不同站台是不同的人或紀錄，放在一起 upsert 會互相覆蓋。
水位線也必須各站台分開算：放在一起時，某個站台斷線期間另一個站台
仍會把水位線往前推，斷線那段就會被跳過。

⚠️ incremental_key 為什麼是 ModifiedDate 而不是 CreatedDate
------------------------------------------------------------------
Citrix 的資料列會就地更新 —— 例如 session 開始時先寫入一列，
結束時才回填 EndDate、ExitCode。用 CreatedDate 當水位線的話，
這些後續更新永遠抓不到，EndDate 會一直是空的。

五張表都有 ModifiedDate，任何異動都會更新它，用它當依據才收得到。

⚠️ lookback_days 的上限
------------------------------------------------------------------
回溯視窗採 upsert，視窗內既有的資料不會被刪除，只是重新比對一次，
所以拉長視窗不會造成資料遺失，代價只是多比對幾筆。
上限存在的理由是避免無意義的大範圍掃描，不是資料安全。
"""

# 站台前綴 → 名稱與用途
#
#   label        log 的站台標頭、通知裡的分組名稱
#   description  站台提供的服務與來源 DB，給人看的說明
#
# 連線資訊放在 .env：CITRIX_<前綴大寫>_HOST、CITRIX_<前綴大寫>_DB，
# 帳號密碼三站共用 CITRIX_USER、CITRIX_PASSWORD。
CITRIX_SITES = {
    "administration": {
        "label": "行政系統",
        "description": "校務系統、櫃台服務系統、行動辦公室，CitrixFCU01Monitoring",
    },
    "statistics_computing": {
        "label": "統計與數值計算軟體",
        "description": "SPSS、SAS、MATLAB 等，CitrixFCU02Monitoring",
    },
    "design_engineering": {
        "label": "設計與工程軟體",
        "description": "AutoCAD、SOLIDWORKS、ANSYS 等，GPU 主機，CitrixFCUVDIMonitoring1",
    },
}

# 來源表 → RAW 表名（不含站台前綴）與自然鍵
SOURCE_TABLES = {
    "application":        ("MonitorData.Application",         ["Id"]),
    "application_launch": ("MonitorData.ApplicationInstance", ["Id"]),
    "session":            ("MonitorData.Session",             ["SessionKey"]),
    "user_account":       ("MonitorData.[User]",              ["Id"]),
    "connection":         ("MonitorData.Connection",          ["Id"]),
}

# table key 為 <站台前綴>_<表名>，例如 administration_session，
# 對應 RAW 表 citrix.administration_session
RAW_TABLES = {
    f"{site}_{table}": {
        "site": site,
        "table": table,
        "original_table": original_table,
        "target_table": f"citrix.{site}_{table}",
        "key_cols": key_cols,
        "incremental_key": "ModifiedDate",
    }
    for site in CITRIX_SITES
    for table, (original_table, key_cols) in SOURCE_TABLES.items()
}

# 回溯視窗預設天數
DEFAULT_LOOKBACK_DAYS = 30

# 上限，超過就拒絕執行（避免無意義的大範圍掃描）
MAX_LOOKBACK_DAYS = 60
