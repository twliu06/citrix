"""
RAW 層來源表設定

來源：CitrixFCU02Monitoring（SQL Server）的 MonitorData schema

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

RAW_TABLES = {
    "application": {
        "source": "citrix",
        "original_table": "MonitorData.Application",
        "target_table": "citrix.application",
        "key_cols": ["Id"],
        "incremental_key": "ModifiedDate",
    },
    "application_launch": {
        "source": "citrix",
        "original_table": "MonitorData.ApplicationInstance",
        "target_table": "citrix.application_launch",
        "key_cols": ["Id"],
        "incremental_key": "ModifiedDate",
    },
    "session": {
        "source": "citrix",
        "original_table": "MonitorData.Session",
        "target_table": "citrix.session",
        "key_cols": ["SessionKey"],
        "incremental_key": "ModifiedDate",
    },
    "user_account": {
        "source": "citrix",
        "original_table": "MonitorData.[User]",
        "target_table": "citrix.user_account",
        "key_cols": ["Id"],
        "incremental_key": "ModifiedDate",
    },
    "connection": {
        "source": "citrix",
        "original_table": "MonitorData.Connection",
        "target_table": "citrix.connection",
        "key_cols": ["Id"],
        "incremental_key": "ModifiedDate",
    },
}

# 回溯視窗預設天數
DEFAULT_LOOKBACK_DAYS = 30

# 上限，超過就拒絕執行（避免無意義的大範圍掃描）
MAX_LOOKBACK_DAYS = 60
