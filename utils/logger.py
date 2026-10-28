from utils.time_utils import now_taipei


def get_logger():
    """
    建立一個加上台北時間戳記的 print，只輸出到 stdout，不寫檔。

    排程上由 run_etl.sh 把輸出寫進 /var/log/citrix/etl_YYYY-MM-DD.log，
    並負責清除逾期的檔。這裡若再寫一份，同樣的內容會存在兩個地方，
    而且這一份不會被清。
    """

    def _log(msg: str):
        print(f"[{now_taipei().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

    return _log
