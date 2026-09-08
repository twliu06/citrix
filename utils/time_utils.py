from datetime import datetime
import pytz

TZ_TAIPEI = pytz.timezone("Asia/Taipei")


def now_taipei():
    return datetime.now(TZ_TAIPEI)


def now_taipei_str():
    return now_taipei().strftime("%Y-%m-%d %H:%M:%S")