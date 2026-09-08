"""
RAW 層增量 ETL —— diff / upsert

流程
----
1. 讀目標表的水位線 MAX(incremental_key)
2. 從水位線往回退 lookback_days 天，得到視窗起點
3. 從來源撈「>= 視窗起點」的資料
4. 依來源自然鍵 upsert：新的 INSERT、有變的 UPDATE、沒變的完全不動

⚠️ 為什麼要回溯視窗而不是嚴格的 > 水位線
------------------------------------------------
Citrix 的資料列會就地更新（session 結束時才回填 EndDate、ExitCode），
更新時 ModifiedDate 會往後跳。若只抓「比水位線更新」的資料，
那些在水位線通過後才被改動的列就會被永遠跳過。
每次重新比對最近 N 天可讓這類更新自動補上。

⚠️ 為什麼不用「刪除區間再整批寫回」
------------------------------------------------
那樣會讓沒有任何變動的列拿到新的 id，updated_at 也被無意義地刷新，
log 更看不出到底有沒有東西真的改變。改用 upsert 之後：
    - 沒變的列完全不會被寫入（被 WHERE ... IS DISTINCT FROM 擋下）
    - id 保持穩定
    - updated_at 的語意是「內容最後變動的時間」
    - 可以明確報出新增 / 更新 / 未變動各幾筆
"""

from datetime import timedelta

from psycopg2.extras import execute_values

from config.raw_tables import DEFAULT_LOOKBACK_DAYS, MAX_LOOKBACK_DAYS
from utils.db_citrix import get_conn as get_citrix_conn
from utils.db_raw import get_conn as get_raw_conn
from utils.time_utils import now_taipei, taipei_to_utc, utc_to_taipei


def get_target_columns(cur, table_name: str) -> dict[str, str]:
    """取得目標表的欄位名與資料型別（排除系統欄位），順序為 ordinal_position"""
    schema_name, table = table_name.split(".", 1)

    cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
          AND column_name NOT IN ('id', 'created_at', 'updated_at')
        ORDER BY ordinal_position
        """,
        (schema_name, table),
    )

    return {row[0]: row[1] for row in cur.fetchall()}


def fetch_source_rows(original_table, inc_key, window_start, columns, print_log):
    """從 Citrix 來源撈資料，回傳 (欄位名 list, 資料列 list)"""
    col_list = ", ".join(f"[{c}]" for c in columns)
    sql = f"SELECT {col_list} FROM {original_table}"

    params = ()
    if window_start:
        sql += f" WHERE [{inc_key}] >= ?"
        params = (window_start,)

    with get_citrix_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        names = [c[0] for c in cur.description]
        rows = cur.fetchall()

    print_log(f"📦 來源回傳 {len(rows)} 筆")

    return names, rows


def coerce(value, data_type):
    """
    RAW 層型態：時間欄位轉成台北時間，其餘轉字串。

    Citrix 來源的時間欄位全部是 UTC 且無時區標記，這裡一律轉成
    Asia/Taipei —— 倉儲內禁止儲存 UTC，避免同一列裡 created_at
    是台北、來源欄位卻是 UTC 的混用情況。

    非時間欄位一定要先轉成 str，PostgreSQL 不會自動把其他型別
    指派給 text 欄位。
    """
    if value is None:
        return None

    if data_type.startswith("timestamp") or data_type == "date":
        return utc_to_taipei(value)

    return str(value)


def build_upsert_sql(target_table, columns, key_cols):
    """
    組出 upsert 語句。

    未變動的列會被 DO UPDATE 的 WHERE 擋下，完全不寫入。
    created_at 不放進 SET —— 那是首次寫入時間，不該被更新覆蓋。

    RETURNING (xmax = 0)：PostgreSQL 對 INSERT 產生的列 xmax 為 0，
    被 UPDATE 的列則不為 0，用來區分新增與更新。
    被 WHERE 擋下的列不會出現在 RETURNING 裡。
    """
    all_cols = columns + ["created_at", "updated_at"]
    quoted_all = ", ".join(f'"{c}"' for c in all_cols)
    quoted_keys = ", ".join(f'"{c}"' for c in key_cols)

    # 非鍵欄位才需要更新
    update_cols = [c for c in columns if c not in key_cols]

    set_clause = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)
    set_clause += ', "updated_at" = EXCLUDED."updated_at"'

    tgt_tuple = ", ".join(f'{target_table}."{c}"' for c in update_cols)
    exc_tuple = ", ".join(f'EXCLUDED."{c}"' for c in update_cols)

    return f"""
        INSERT INTO {target_table} ({quoted_all})
        VALUES %s
        ON CONFLICT ({quoted_keys}) DO UPDATE SET
            {set_clause}
        WHERE ({tgt_tuple}) IS DISTINCT FROM ({exc_tuple})
        RETURNING (xmax = 0) AS inserted
    """


def run_incremental_etl(table_key, cfg, print_log, lookback_days=None):
    target_table = cfg["target_table"]
    original_table = cfg["original_table"]
    inc_key = cfg["incremental_key"]
    key_cols = cfg["key_cols"]

    if lookback_days is None:
        lookback_days = cfg.get("lookback_days", DEFAULT_LOOKBACK_DAYS)

    if lookback_days > MAX_LOOKBACK_DAYS:
        raise ValueError(
            f"❌ {table_key} 的 lookback_days={lookback_days} 超過上限 "
            f"{MAX_LOOKBACK_DAYS} 天（避免無意義的大範圍掃描）"
        )

    conn = get_raw_conn(autocommit=False)

    try:
        with conn.cursor() as cur:
            col_types = get_target_columns(cur, target_table)
            if not col_types:
                raise ValueError(f"找不到目標表或欄位：{target_table}")

            columns = list(col_types.keys())

            missing_keys = [k for k in key_cols if k not in columns]
            if missing_keys:
                raise ValueError(
                    f"{target_table} 缺少設定的自然鍵欄位：{missing_keys}"
                )

            # 1️⃣ 水位線
            cur.execute(f'SELECT MAX("{inc_key}") FROM {target_table}')
            max_val = cur.fetchone()[0]

            if max_val:
                window_start = max_val - timedelta(days=lookback_days)
                print_log(
                    f"📈 上次同步至 {max_val}（台北），回溯 {lookback_days} 天 "
                    f"→ 比對 {window_start} 之後的資料"
                )
            else:
                window_start = None
                print_log("🚀 目標表為空，執行全量初始化")

            # 2️⃣ 撈來源
            #
            # ⚠️ 水位線取自 RAW，已是台北時間；Citrix 來源是 UTC，
            #    送過去之前必須轉回 UTC。少了這一步等於用「未來 8 小時」
            #    的條件去查，會查不到任何資料而讓管線靜默停擺。
            names, rows = fetch_source_rows(
                original_table, inc_key, taipei_to_utc(window_start),
                columns, print_log
            )

            if names != columns:
                only_src = [c for c in names if c not in columns]
                only_tgt = [c for c in columns if c not in names]
                raise ValueError(
                    f"{target_table} 欄位對不上：\n"
                    f"  來源有、目標沒有：{only_src}\n"
                    f"  目標有、來源沒有：{only_tgt}\n"
                    f"  → 目標表應為來源的鏡射，請補進 create_table.py 並 ALTER"
                )

            if not rows:
                print_log("⏸️ 來源無資料，目標表不做任何異動")
                conn.rollback()
                return

            # 3️⃣ upsert
            now = now_taipei().replace(tzinfo=None)
            values = [
                tuple(coerce(v, col_types[c]) for c, v in zip(columns, row))
                + (now, now)
                for row in rows
            ]

            result = execute_values(
                cur,
                build_upsert_sql(target_table, columns, key_cols),
                values,
                page_size=1000,
                fetch=True,
            )

            inserted = sum(1 for r in result if r[0])
            updated = len(result) - inserted
            unchanged = len(values) - len(result)

            conn.commit()

            print_log(
                f"🔄 比對 {len(values)} 筆："
                f"新增 {inserted}、更新 {updated}、未變動 {unchanged}"
            )

            cur.execute(f'SELECT COUNT(*), MAX("{inc_key}") FROM {target_table}')
            total, new_wm = cur.fetchone()
            print_log(f"✅ {target_table} 完成，累計 {total} 筆，水位線 {new_wm}")

    except Exception as e:
        conn.rollback()
        print_log(f"❌ {table_key} 同步失敗，已 rollback: {e}")
        raise

    finally:
        conn.close()
