import os
import pyodbc
from dotenv import load_dotenv

# 讀取 .env
load_dotenv()

# =========================
# Citrix 監控資料庫設定（來源，唯讀）
# =========================
DB_CONFIG = {
    "host": os.getenv("CITRIX_HOST"),
    "database": os.getenv("CITRIX_DB"),
    "user": os.getenv("CITRIX_USER"),
    "password": os.getenv("CITRIX_PASSWORD"),
    "driver": "ODBC Driver 18 for SQL Server",
}

CONN_STR = (
    f"DRIVER={{{DB_CONFIG['driver']}}};"
    f"SERVER={DB_CONFIG['host']};"
    f"DATABASE={DB_CONFIG['database']};"
    f"UID={DB_CONFIG['user']};"
    f"PWD={DB_CONFIG['password']};"
    "TrustServerCertificate=yes;"
)


# =========================
# pyodbc：查詢用
# =========================
def get_conn(timeout: int = 30):
    """
    Citrix 監控資料庫連線（SQL Server）

    僅供讀取，不對來源做任何寫入。
    """
    return pyodbc.connect(CONN_STR, timeout=timeout)
