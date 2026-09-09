from utils.db_raw import get_conn

TABLE_NAME = "citrix.connection"
TABLE_COMMENT = "連線紀錄（來源：MonitorData.Connection）"

# RAW 層：
#   1. 欄位名稱完全照抄來源基底表（SQL Server 駝峰式），
#      PostgreSQL 需以雙引號保留大小寫
#   2. 時間欄位用 TIMESTAMP(6)，其餘一律 TEXT
#   3. 除系統欄位外皆可為空 —— RAW 的職責是收得進來，不是擋資料
#   4. 欄位順序照抄來源
#
# (欄位名稱, 型別, NOT NULL, 欄位註解)
COLUMNS = [
    ("id", "BIGSERIAL PRIMARY KEY", True, "連線紀錄識別碼"),

    ("Id",                        "TEXT",          False, "來源連線識別碼"),
    ("ClientName",                "TEXT",          False, "用戶端裝置名稱"),
    ("ClientAddress",             "TEXT",          False, "用戶端 IP"),
    ("ClientVersion",             "TEXT",          False, "用戶端版本"),
    ("ClientPlatform",            "TEXT",          False, "用戶端平台"),
    ("ConnectedViaHostName",      "TEXT",          False, "連線經由的主機名稱"),
    ("ConnectedViaIPAddress",     "TEXT",          False, "連線經由的 IP"),
    ("LaunchedViaHostName",       "TEXT",          False, "啟動經由的主機名稱"),
    ("LaunchedViaIPAddress",      "TEXT",          False, "啟動經由的 IP"),
    ("IsReconnect",               "TEXT",          False, "是否為重新連線"),
    ("IsSecureIca",               "TEXT",          False, "是否使用 SecureICA 加密"),
    ("Protocol",                  "TEXT",          False, "連線協定"),
    ("LogOnStartDate",            "TIMESTAMP(6)",  False, "登入開始時間"),
    ("LogOnEndDate",              "TIMESTAMP(6)",  False, "登入結束時間"),
    ("BrokeringDuration",         "TEXT",          False, "代理配發耗時（毫秒）"),
    ("BrokeringDate",             "TIMESTAMP(6)",  False, "代理配發時間"),
    ("DisconnectCode",            "TEXT",          False, "中斷連線代碼"),
    ("DisconnectDate",            "TIMESTAMP(6)",  False, "中斷連線時間"),
    ("VMStartStartDate",          "TIMESTAMP(6)",  False, "虛擬機開機開始時間"),
    ("VMStartEndDate",            "TIMESTAMP(6)",  False, "虛擬機開機結束時間"),
    ("ClientSessionValidateDate", "TIMESTAMP(6)",  False, "用戶端工作階段驗證時間"),
    ("ServerSessionValidateDate", "TIMESTAMP(6)",  False, "伺服器工作階段驗證時間"),
    ("EstablishmentDate",         "TIMESTAMP(6)",  False, "連線建立時間"),
    ("HdxStartDate",              "TIMESTAMP(6)",  False, "HDX 連線開始時間"),
    ("HdxEndDate",                "TIMESTAMP(6)",  False, "HDX 連線結束時間"),
    ("AuthenticationDuration",    "TEXT",          False, "認證耗時（毫秒）"),
    ("GpoStartDate",              "TIMESTAMP(6)",  False, "群組原則套用開始時間"),
    ("GpoEndDate",                "TIMESTAMP(6)",  False, "群組原則套用結束時間"),
    ("LogOnScriptsStartDate",     "TIMESTAMP(6)",  False, "登入指令碼開始時間"),
    ("LogOnScriptsEndDate",       "TIMESTAMP(6)",  False, "登入指令碼結束時間"),
    ("ProfileLoadStartDate",      "TIMESTAMP(6)",  False, "使用者設定檔載入開始時間"),
    ("ProfileLoadEndDate",        "TIMESTAMP(6)",  False, "使用者設定檔載入結束時間"),
    ("InteractiveStartDate",      "TIMESTAMP(6)",  False, "互動階段開始時間"),
    ("InteractiveEndDate",        "TIMESTAMP(6)",  False, "互動階段結束時間"),
    ("SessionKey",                "TEXT",          False, "工作階段識別碼"),
    ("CreatedDate",               "TIMESTAMP(6)",  False, "來源建立時間"),
    ("ModifiedDate",              "TIMESTAMP(6)",  False, "來源更新時間，增量抽取依據"),

    ("created_at", "TIMESTAMP(6)", True, "資料建立時間"),
    ("updated_at", "TIMESTAMP(6)", True, "資料更新時間"),
]

# 來源自然鍵 —— 增量 upsert 的比對依據
UNIQUE_KEYS = ["Id"]

# 增量抽取的水位線查詢
INDEXES = [
    ("idx_connection_modified", ['"ModifiedDate"']),
]


def build_create_table_sql() -> str:
    col_defs = []

    for name, dtype, not_null, _ in COLUMNS:
        nn = " NOT NULL" if not_null and "PRIMARY KEY" not in dtype else ""
        col_defs.append(f'    "{name}" {dtype}{nn}')

    columns_sql = ",\n".join(col_defs)

    return (
        f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} (\n"
        f"{columns_sql}\n"
        ");"
    )


def build_index_sql() -> list[str]:
    key_cols = ", ".join(f'"{k}"' for k in UNIQUE_KEYS)

    # 用 unique index 而非 constraint：CREATE ... IF NOT EXISTS 可重複執行，
    # ON CONFLICT 也吃 unique index
    stmts = [
        f"CREATE UNIQUE INDEX IF NOT EXISTS uq_connection_key "
        f"ON {TABLE_NAME} ({key_cols});"
    ]

    stmts += [
        f"CREATE INDEX IF NOT EXISTS {name} ON {TABLE_NAME} ({', '.join(cols)});"
        for name, cols in INDEXES
    ]

    return stmts


def build_comment_sql() -> list[str]:
    stmts = [f"COMMENT ON TABLE {TABLE_NAME} IS '{TABLE_COMMENT}';"]

    for name, _, _, comment in COLUMNS:
        if comment:
            stmts.append(
                f'COMMENT ON COLUMN {TABLE_NAME}."{name}" IS \'{comment}\';'
            )

    return stmts


def main():
    with get_conn(autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(build_create_table_sql())

            for stmt in build_index_sql():
                cur.execute(stmt)

            for stmt in build_comment_sql():
                cur.execute(stmt)

            print(f"✅ {TABLE_NAME} 建表完成")


if __name__ == "__main__":
    main()
