from utils.db_raw import get_conn

TABLE_NAME = "citrix.session"
TABLE_COMMENT = "工作階段紀錄 (原始資料)(原表名: MonitorData.Session)"

# RAW 層：
#   1. 欄位名稱完全照抄來源基底表（SQL Server 駝峰式），
#      PostgreSQL 需以雙引號保留大小寫
#   2. 時間欄位用 TIMESTAMP(6)，其餘一律 TEXT
#   3. 除系統欄位外皆可為空 —— RAW 的職責是收得進來，不是擋資料
#   4. 欄位順序照抄來源
#
# (欄位名稱, 型別, NOT NULL, 欄位註解)
COLUMNS = [
    ("id", "BIGSERIAL PRIMARY KEY", True, "工作階段紀錄識別碼"),

    ("SessionKey",                "TEXT",          False, "工作階段識別碼"),
    ("StartDate",                 "TIMESTAMP(6)",  False, "工作階段開始時間"),
    ("LogOnDuration",             "TEXT",          False, "登入耗時（毫秒）"),
    ("EndDate",                   "TIMESTAMP(6)",  False, "工作階段結束時間"),
    ("ExitCode",                  "TEXT",          False, "結束代碼"),
    ("FailureDate",               "TIMESTAMP(6)",  False, "失敗發生時間"),
    ("ConnectionState",           "TEXT",          False, "連線狀態代碼"),
    ("ConnectionStateChangeDate", "TIMESTAMP(6)",  False, "連線狀態變更時間"),
    ("LifecycleState",            "TEXT",          False, "生命週期狀態代碼"),
    ("CurrentConnectionId",       "TEXT",          False, "目前連線識別碼"),
    ("UserId",                    "TEXT",          False, "使用者識別碼"),
    ("MachineId",                 "TEXT",          False, "機器識別碼"),
    ("SessionType",               "TEXT",          False, "工作階段類型代碼（應用程式／桌面）"),
    ("IsAnonymous",               "TEXT",          False, "是否為匿名工作階段"),
    ("CreatedDate",               "TIMESTAMP(6)",  False, "來源建立時間"),
    ("ModifiedDate",              "TIMESTAMP(6)",  False, "來源更新時間，增量抽取依據"),
    ("FailureId",                 "TEXT",          False, "失敗原因代碼"),
    ("SessionIdleTime",           "TIMESTAMP(6)",  False, "閒置時間"),

    ("created_at", "TIMESTAMP(6)", True, "資料建立時間"),
    ("updated_at", "TIMESTAMP(6)", True, "資料更新時間"),
]

# 來源自然鍵 —— 增量 upsert 的比對依據
UNIQUE_KEYS = ["SessionKey"]

# 增量抽取的水位線查詢
INDEXES = [
    ("idx_session_modified", ['"ModifiedDate"']),
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
        f"CREATE UNIQUE INDEX IF NOT EXISTS uq_session_key "
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
