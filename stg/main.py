"""
STG 層 ETL 主程式

用法：
    python -m stg.main

做法：從 RAW 撈出加工後的結果，整表重建 STG。
先把資料全部讀完才動目標表，來源查詢失敗時 STG 完全不受影響；
TRUNCATE 與寫入在同一個交易內完成，中途失敗不會留下空表。
"""

import os

import psycopg2
from psycopg2.extras import execute_values

from config.stg_tables import COLUMNS, SOURCE_SQL, TARGET_TABLE
from utils.db_raw import get_conn as get_raw_conn
from utils.db_stg import get_conn as get_stg_conn
from utils.logger import get_logger
from utils.time_utils import now_taipei

BASE_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(BASE_DIR, "logs")

# TRUNCATE 取不到鎖時的等待上限，超過就放棄並報錯（見 main() 內的說明）
LOCK_TIMEOUT = "60s"

print_log = get_logger(log_dir=LOG_DIR, log_prefix="stg_citrix")


def main():
    # 1️⃣ 先把資料全部讀出來，讀完才動目標表
    raw_conn = get_raw_conn()
    try:
        with raw_conn.cursor() as cur:
            cur.execute(SOURCE_SQL)
            names = [d[0] for d in cur.description]
            rows = cur.fetchall()
    finally:
        raw_conn.close()

    print_log(f"📦 從 RAW 取得 {len(rows)} 筆")

    if names != COLUMNS:
        raise ValueError(
            f"{TARGET_TABLE} 欄位對不上：\n"
            f"  SQL 回傳：{names}\n"
            f"  設定期望：{COLUMNS}"
        )

    if not rows:
        print_log("⏸️ 來源無資料，保留原表不做重建")
        return

    # 2️⃣ 單一交易內：清空 + 寫入
    now = now_taipei().replace(tzinfo=None)
    insert_cols = COLUMNS + ["created_at", "updated_at"]
    values = [tuple(r) + (now, now) for r in rows]

    conn = get_stg_conn(autocommit=False)
    try:
        with conn.cursor() as cur:
            # TRUNCATE 需要 ACCESS EXCLUSIVE 鎖，任何一個對本表開著的交易都擋得住它，
            # 連純 SELECT 也算。預設會無聲排隊到對方結束 —— 曾經因此卡了 18 分鐘，
            # 而 log 上完全看不出在等什麼。設了上限就會立刻報錯說明原因。
            cur.execute(f"SET lock_timeout = '{LOCK_TIMEOUT}'")

            cur.execute(f"TRUNCATE TABLE {TARGET_TABLE} RESTART IDENTITY")

            execute_values(
                cur,
                f"INSERT INTO {TARGET_TABLE} ({', '.join(insert_cols)}) VALUES %s",
                values,
                page_size=1000,
            )

            conn.commit()

            cur.execute(f"SELECT COUNT(*) FROM {TARGET_TABLE}")
            print_log(f"✅ {TARGET_TABLE} 重建完成，共 {cur.fetchone()[0]} 筆")

    except psycopg2.errors.LockNotAvailable:
        conn.rollback()
        print_log(
            f"❌ {LOCK_TIMEOUT} 內取不到 {TARGET_TABLE} 的鎖，已 rollback。"
            "整表重建需要 ACCESS EXCLUSIVE，表示有其他交易正握著這張表；"
            "查 pg_locks 與 pg_stat_activity 可以找出是誰。"
        )
        raise

    except Exception as e:
        conn.rollback()
        print_log(f"❌ 重建失敗，已 rollback: {e}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
