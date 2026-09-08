from utils.db_stg import get_conn

TABLE_NAME = "private.citrix_software_usage"
TABLE_COMMENT = "Citrix 雲端軟體使用紀錄"

# (欄位名稱, 資料型態, NOT NULL, 欄位註解)
COLUMNS = [
    ("software_usage_id", "BIGSERIAL PRIMARY KEY", True, "軟體使用紀錄識別碼"),

    # === 使用者 ===
    ("user_identifier", "VARCHAR(20)", True, "使用者證號"),
    ("user_id", "BIGINT", True, "使用者識別碼"),

    # === 軟體 ===
    ("app_name", "VARCHAR(100)", True, "軟體名稱"),
    ("app_id", "UUID", True, "軟體識別碼"),

    # === 連線 ===
    ("session_key", "UUID", True, "工作階段識別碼"),
    ("client_ip", "VARCHAR(50)", False, "用戶端 IP"),

    # === 時間（登入 → 工作階段 → 軟體）===
    ("logon_started_at", "TIMESTAMP(6)", False, "登入開始時間"),
    ("logon_ended_at", "TIMESTAMP(6)", False, "登入結束時間"),
    ("session_started_at", "TIMESTAMP(6)", False, "工作階段開始時間"),
    ("session_ended_at", "TIMESTAMP(6)", False, "工作階段結束時間"),
    ("app_started_at", "TIMESTAMP(6)", False, "軟體啟動時間"),
    ("app_ended_at", "TIMESTAMP(6)", False, "軟體結束時間"),

    ("created_at", "TIMESTAMP(6)", True, "資料建立時間"),
    ("updated_at", "TIMESTAMP(6)", True, "資料更新時間"),
]

# ⚠️ 本表沒有唯一鍵
#
# 來源 SQL 未選出 ApplicationInstance.Id，而多進程應用（例如
# WorkFlow ERP GP 系統）會在同一毫秒產生多筆 instance，
# 這些列在來源是不同紀錄（Id 不同），投影成這 12 欄之後完全相同。
# 實測 3,184 列中有 44 列屬於這種情況。
#
# 因此本表改用整表重建，不做 key 比對。RAW 層保有完整歷史，
# STG 隨時可以重算，重建不會造成資料遺失。
UNIQUE_KEYS = []

INDEXES = [
    ("idx_citrix_software_usage_app_started", ["app_started_at"]),
    ("idx_citrix_software_usage_user", ["user_identifier"]),
]


def build_create_table_sql() -> str:
    col_defs = []

    for name, dtype, not_null, _ in COLUMNS:
        nn = " NOT NULL" if not_null and "PRIMARY KEY" not in dtype else ""
        col_defs.append(f"    {name} {dtype}{nn}")

    if UNIQUE_KEYS:
        col_defs.append(f"    UNIQUE ({', '.join(UNIQUE_KEYS)})")

    columns_sql = ",\n".join(col_defs)

    return (
        f"CREATE TABLE IF NOT EXISTS {TABLE_NAME} (\n"
        f"{columns_sql}\n"
        ");"
    )


def build_index_sql() -> list[str]:
    return [
        f"CREATE INDEX IF NOT EXISTS {name} ON {TABLE_NAME} ({', '.join(cols)});"
        for name, cols in INDEXES
    ]


def build_comment_sql() -> list[str]:
    stmts = [f"COMMENT ON TABLE {TABLE_NAME} IS '{TABLE_COMMENT}';"]

    for name, _, _, comment in COLUMNS:
        if comment:
            stmts.append(
                f"COMMENT ON COLUMN {TABLE_NAME}.{name} IS '{comment}';"
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
