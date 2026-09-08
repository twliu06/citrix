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
回溯視窗會先 DELETE 目標表的切片再重載。若視窗長度超過來源保留期
（約 90 天），被刪掉的舊資料在來源已經不存在，就再也載不回來。
視窗務必遠小於 90 天，預設 30 天。
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

# 回溯視窗預設天數，必須遠小於來源保留期（約 90 天）
DEFAULT_LOOKBACK_DAYS = 30

# 安全上限，超過就拒絕執行（避免刪掉來源已無法提供的資料）
MAX_LOOKBACK_DAYS = 60
