import os
import psycopg2
from contextlib import contextmanager
from sqlalchemy import create_engine
from dotenv import load_dotenv

# 讀取 .env
load_dotenv()

# =========================
# DB 設定（單一來源）
# =========================
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT")),
    "dbname": os.getenv("DB_STG_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}

# SQLAlchemy 連線字串（給 pandas / read_sql 用）
DB_URI = (
    f"postgresql+psycopg2://{DB_CONFIG['user']}:"
    f"{DB_CONFIG['password']}@"
    f"{DB_CONFIG['host']}:"
    f"{DB_CONFIG['port']}/"
    f"{DB_CONFIG['dbname']}"
)

# =========================
# psycopg2：寫入 / 建表用
# =========================
def get_conn(autocommit: bool = True):
    """
    psycopg2 connection（給 ETL / insert / update）
    """
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = autocommit
    return conn


# =========================
# SQLAlchemy engine：查詢用
# =========================
_ENGINE = None

def get_engine():
    """
    給：
    - pandas.read_sql
    - 任何需要「讀 DB → DataFrame」的地方

    單例（singleton），避免重複建立連線池
    """
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_engine(DB_URI)
    return _ENGINE