import os
import pyodbc
from dotenv import load_dotenv

# 讀取 .env
load_dotenv()

DRIVER = "ODBC Driver 18 for SQL Server"


# =========================
# Citrix 監控資料庫設定（來源，唯讀）
#
# 三個站台各有一個監控資料庫，連線資訊依站台前綴取自 .env：
#   CITRIX_<前綴大寫>_HOST、CITRIX_<前綴大寫>_DB
# 帳號密碼三站共用 CITRIX_USER、CITRIX_PASSWORD。
# 站台清單見 config/raw_tables.py 的 CITRIX_SITES。
# =========================
def site_database(site: str):
    """站台的監控資料庫名稱（.env 的 CITRIX_<前綴大寫>_DB），未設定時為 None"""
    return os.getenv(f"CITRIX_{site.upper()}_DB")


def site_title(site: str) -> str:
    """
    站台標頭：中文名稱（資料庫名），例如「行政系統（CitrixFCU01Monitoring）」

    資料庫名取自 .env，與實際連線的是同一個值。
    run_etl.sh 以這個標頭把 log 依站台分組，格式改動時要一併修改。
    """
    from config.raw_tables import CITRIX_SITES

    database = site_database(site) or f".env 未設定 CITRIX_{site.upper()}_DB"
    return f"{CITRIX_SITES[site]['label']}（{database}）"


def build_conn_str(site: str) -> str:
    prefix = f"CITRIX_{site.upper()}"
    host = os.getenv(f"{prefix}_HOST")
    database = site_database(site)

    if not host or not database:
        raise ValueError(f".env 缺少 {prefix}_HOST 或 {prefix}_DB")

    return (
        f"DRIVER={{{DRIVER}}};"
        f"SERVER={host};"
        f"DATABASE={database};"
        f"UID={os.getenv('CITRIX_USER')};"
        f"PWD={os.getenv('CITRIX_PASSWORD')};"
        "TrustServerCertificate=yes;"
    )


# =========================
# pyodbc：查詢用
# =========================
def get_conn(site: str, timeout: int = 30):
    """
    Citrix 監控資料庫連線（SQL Server）

    僅供讀取，不對來源做任何寫入。
    """
    return pyodbc.connect(build_conn_str(site), timeout=timeout)
