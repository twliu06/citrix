# 釘住 Debian 版本（bookworm），不要用浮動的 python:3.11-slim。
# 因為下面的 ODBC 套件庫路徑是綁 Debian 版本的，
# base image 若跟著 upstream 升到 trixie，套件庫來源會失效而 build 失敗。
FROM python:3.11-slim-bookworm

WORKDIR /app

COPY requirements.txt .

# ODBC driver manager
RUN apt-get update && apt-get install -y \
    unixodbc \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Microsoft ODBC Driver 18 for SQL Server
#
# msodbcsql18 可自由散布，直接裝進 image —— 不必假設主機裝了什麼，
# 換一台機器也能跑。
#
# 驅動程式註冊在 image 的 /etc/odbcinst.ini。docker-compose.yml 若掛載
# 主機的同名檔，會蓋掉這裡的註冊，讓容器找不到 Driver 18。
#
# 驅動程式名稱要與 utils/db_citrix.py 的 CITRIX_DRIVER 預設值一致。
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl gnupg ca-certificates \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
      | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg] \
https://packages.microsoft.com/debian/12/prod bookworm main" \
      > /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
 && apt-get purge -y curl gnupg \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

# build 時就確認驅動程式註冊成功，不要等到排程半夜跑才發現
RUN odbcinst -q -d | grep -q "ODBC Driver 18 for SQL Server"

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ODBC 設定檔位置
ENV ODBCINI=/etc/odbc.ini
ENV ODBCSYSINI=/etc

# 這個容器是常駐待命，啟動時不執行任何 ETL。
#
# 實際的排程由主機的 cron 以 docker exec 驅動，定義在 deploy/cron.d/citrix。
# docker-compose.yml 也設了同樣的 command，這裡保持一致，
# 讓不透過 compose 直接啟動這個 image 時行為也相同。
CMD ["tail", "-f", "/dev/null"]
