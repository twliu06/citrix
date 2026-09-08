import os
from datetime import datetime
from typing import Optional
from utils.time_utils import now_taipei


def get_logger(
    log_dir: str,
    log_prefix: Optional[str] = None,
):
    """
    建立一個簡單的 print + file logger

    Parameters
    ----------
    log_dir : str
        log 資料夾路徑（不存在會自動建立）
    log_prefix : str | None
        log 檔名前綴，例如 raw_campus_meter_daily
        若為 None，則使用資料夾名稱
    """
    os.makedirs(log_dir, exist_ok=True)

    if log_prefix is None:
        log_prefix = os.path.basename(os.path.normpath(log_dir))

    log_file = os.path.join(
        log_dir,
        f"{log_prefix}_{now_taipei().strftime('%Y-%m-%d')}.log"
    )

    def _log(msg: str):
        timestamped_msg = f"[{now_taipei().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        print(timestamped_msg)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(timestamped_msg + "\n")

    return _log
