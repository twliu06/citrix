"""
RAW 層 ETL 主程式（五張表共用）

用法：
    python -m raw.main all                  全部五張
    python -m raw.main session connection   指定表
"""

import os
import sys

from config.raw_tables import RAW_TABLES
from utils.incremental_etl import run_incremental_etl
from utils.logger import get_logger

BASE_DIR = os.path.dirname(__file__)
LOG_DIR = os.path.join(BASE_DIR, "logs")

print_log = get_logger(log_dir=LOG_DIR, log_prefix="raw_citrix")


def main(table_keys=None, all_tables=False):
    if all_tables:
        table_keys = list(RAW_TABLES.keys())
        print_log(f"🚀 將跑 RAW_TABLES 全部 {len(table_keys)} 張表")
    elif not table_keys:
        print_log("⚠️ 請指定要跑的 table key 或使用 all")
        return

    failed = []

    for table_key in table_keys:
        if table_key not in RAW_TABLES:
            print_log(f"⚠️ {table_key} 不在 RAW_TABLES 設定中，跳過")
            continue

        cfg = RAW_TABLES[table_key]
        print_log(f"───── {table_key} ─────")

        try:
            run_incremental_etl(table_key, cfg, print_log)
        except Exception:
            # 單張表失敗不中斷其餘表，最後統一回報
            failed.append(table_key)

    if failed:
        print_log(f"❌ 以下表同步失敗：{failed}")
        sys.exit(1)

    print_log("🎉 Citrix RAW 同步完成")


if __name__ == "__main__":
    args = sys.argv[1:]

    if args and args[0].lower() == "all":
        main(all_tables=True)
    elif args:
        main(table_keys=args)
    else:
        print("用法:")
        print("  python -m raw.main all                  全部五張")
        print("  python -m raw.main session connection   指定表")
        print()
        print("可用的 table key:")
        for k, v in RAW_TABLES.items():
            print(f"  {k:<20} ← {v['original_table']}")
