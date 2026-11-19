"""
RAW 層 ETL 主程式（三個站台、各五張表共用）

用法：
    python -m raw.main all                          全部站台、全部表
    python -m raw.main administration               指定站台的五張表
    python -m raw.main administration_session       指定表（table key）
"""

import sys

from config.raw_tables import CITRIX_SITES, RAW_TABLES
from utils.db_citrix import site_title
from utils.incremental_etl import run_incremental_etl
from utils.logger import get_logger

print_log = get_logger()


def main(table_keys=None, all_tables=False):
    if all_tables:
        table_keys = list(RAW_TABLES.keys())
        print_log(f"🚀 將跑 RAW_TABLES 全部 {len(table_keys)} 張表")
    elif not table_keys:
        print_log("⚠️ 請指定要跑的 table key、站台前綴或使用 all")
        return
    else:
        # 站台前綴展開成該站台的五張表
        table_keys = [
            key
            for arg in table_keys
            for key in (
                [k for k, c in RAW_TABLES.items() if c["site"] == arg]
                if arg in CITRIX_SITES else [arg]
            )
        ]

    failed = []
    sites = []

    for table_key in table_keys:
        if table_key not in RAW_TABLES:
            print_log(f"⚠️ {table_key} 不在 RAW_TABLES 設定中，跳過")
            continue

        cfg = RAW_TABLES[table_key]

        # 站台標頭：同一站台的表在 table_keys 裡是連續的，換站台時印一次
        if not sites or sites[-1] != cfg["site"]:
            sites.append(cfg["site"])
            print_log(f"═════ {site_title(cfg['site'])} ═════")

        print_log(f"───── {cfg['table']} ─────")

        try:
            run_incremental_etl(table_key, cfg, print_log)
        except Exception:
            # 單張表失敗不中斷其餘表，最後統一回報
            failed.append(table_key)

    if failed:
        # run_etl.sh 讀這三行：失敗的表寫進通知，表全部完成的站台照常跑 STG
        failed_sites = list(dict.fromkeys(RAW_TABLES[k]["site"] for k in failed))
        ok_sites = [s for s in sites if s not in failed_sites]

        print_log(f"❌ 以下表同步失敗：{failed}")
        print_log(f"❌ 以下站台有表同步失敗：{failed_sites}")
        print_log(f"✔️ 以下站台全部表同步完成：{ok_sites}")
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
        print("  python -m raw.main all                          全部站台、全部表")
        print("  python -m raw.main administration               指定站台的五張表")
        print("  python -m raw.main administration_session       指定表")
        print()
        print("可用的站台前綴:")
        for site in CITRIX_SITES:
            print(f"  {site}")
        print()
        print("可用的 table key:")
        for k, v in RAW_TABLES.items():
            print(f"  {k:<40} ← {v['original_table']}")
