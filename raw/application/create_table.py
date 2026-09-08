from utils.db_raw import get_conn

TABLE_NAME = "citrix.application"
TABLE_COMMENT = "應用程式清單 (原始資料)(原表名: MonitorData.Application)"

# RAW 層：
#   1. 欄位名稱完全照抄來源基底表（SQL Server 駝峰式），
#      PostgreSQL 需以雙引號保留大小寫
#   2. 時間欄位用 TIMESTAMP(6)，其餘一律 TEXT
#   3. 除系統欄位外皆可為空 —— RAW 的職責是收得進來，不是擋資料
#   4. 欄位順序照抄來源
#
# (欄位名稱, 型別, NOT NULL, 欄位註解)
COLUMNS = [
    ("id", "BIGSERIAL PRIMARY KEY", True, "應用程式清單識別碼"),

    ("Id",              "TEXT",          False, "應用程式識別碼"),
    ("Name",            "TEXT",          False, "應用程式名稱（不含版本後綴）"),
    ("PublishedName",   "TEXT",          False, "發佈名稱（使用者在 Workspace 看到的名稱）"),
    ("ApplicationType", "TEXT",          False, "應用程式類型代碼"),
    ("Enabled",         "TEXT",          False, "是否啟用"),
    ("AdminFolder",     "TEXT",          False, "管理資料夾路徑"),
    ("LifecycleState",  "TEXT",          False, "生命週期狀態代碼"),
    ("Path",            "TEXT",          False, "執行檔路徑"),
    ("BrowserName",     "TEXT",          False, "Citrix 內部唯一識別名稱"),
    ("CreatedDate",     "TIMESTAMP(6)",  False, "來源建立時間"),
    ("ModifiedDate",    "TIMESTAMP(6)",  False, "來源更新時間，增量抽取依據"),

    ("created_at", "TIMESTAMP(6)", True, "資料建立時間"),
    ("updated_at", "TIMESTAMP(6)", True, "資料更新時間"),
]

# 來源自然鍵 —— 增量 upsert 的比對依據
UNIQUE_KEYS = ["Id"]

# 增量抽取的水位線查詢
INDEXES = [
    ("idx_application_modified", ['"ModifiedDate"']),
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
        f"CREATE UNIQUE INDEX IF NOT EXISTS uq_application_key "
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
