from datetime import datetime
import pytz

TZ_TAIPEI = pytz.timezone("Asia/Taipei")
TZ_UTC = pytz.utc


def now_taipei():
    return datetime.now(TZ_TAIPEI)


def now_taipei_str():
    return now_taipei().strftime("%Y-%m-%d %H:%M:%S")


def utc_to_taipei(dt: datetime | None) -> datetime | None:
    """
    來源端的 UTC 時間轉台北時間，回傳 naive datetime。

    Citrix 監控資料庫的時間欄位全部是 UTC 且沒有時區標記，
    寫進 RAW 之前一律用這個函式轉換 —— 倉儲內禁止儲存 UTC。

    回傳 naive 是因為 RAW / STG 的欄位型別是 TIMESTAMP(6)
    （without time zone），帶 tzinfo 會被 PostgreSQL 再做一次換算。
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = TZ_UTC.localize(dt)

    return dt.astimezone(TZ_TAIPEI).replace(tzinfo=None)


def taipei_to_utc(dt: datetime | None) -> datetime | None:
    """
    台北時間轉回 UTC，回傳 naive datetime。

    增量抽取的水位線取自 RAW（已是台北時間），
    但送回 Citrix 來源查詢時必須是 UTC，否則等於用「未來 8 小時」
    的條件去查，會查不到任何資料而讓管線靜默停擺。
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = TZ_TAIPEI.localize(dt)

    return dt.astimezone(TZ_UTC).replace(tzinfo=None)
