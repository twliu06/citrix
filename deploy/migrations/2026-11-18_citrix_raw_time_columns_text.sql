-- 統計與數值計算軟體站台的 RAW 表：來源時間欄位由 TIMESTAMP(6) 改為 TEXT
--
-- 執行於 raw_cda_prod，須在 2026-11-18_citrix_raw_site_prefix.sql 之後執行（用的是改名後的表名）。
-- 依規範，RAW 的來源欄位一律 TEXT；唯一例外是增量水位線 ModifiedDate，維持 TIMESTAMP(6)。
-- 既有值本來就是台北時間，轉成固定 6 位小數的字串，與 ETL 寫入的格式相同，
-- 之後 upsert 比對時不會把沒變的列誤判成有變。
-- 另外兩個站台的表由 create_table.py 直接以 TEXT 建立，不在本檔。

BEGIN;

ALTER TABLE citrix.statistics_computing_application
    ALTER COLUMN "CreatedDate" TYPE TEXT USING to_char("CreatedDate", 'YYYY-MM-DD HH24:MI:SS.US');

ALTER TABLE citrix.statistics_computing_application_launch
    ALTER COLUMN "StartDate" TYPE TEXT USING to_char("StartDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "EndDate" TYPE TEXT USING to_char("EndDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "CreatedDate" TYPE TEXT USING to_char("CreatedDate", 'YYYY-MM-DD HH24:MI:SS.US');

ALTER TABLE citrix.statistics_computing_session
    ALTER COLUMN "StartDate" TYPE TEXT USING to_char("StartDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "EndDate" TYPE TEXT USING to_char("EndDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "FailureDate" TYPE TEXT USING to_char("FailureDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "ConnectionStateChangeDate" TYPE TEXT USING to_char("ConnectionStateChangeDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "CreatedDate" TYPE TEXT USING to_char("CreatedDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "SessionIdleTime" TYPE TEXT USING to_char("SessionIdleTime", 'YYYY-MM-DD HH24:MI:SS.US');

ALTER TABLE citrix.statistics_computing_user_account
    ALTER COLUMN "CreatedDate" TYPE TEXT USING to_char("CreatedDate", 'YYYY-MM-DD HH24:MI:SS.US');

ALTER TABLE citrix.statistics_computing_connection
    ALTER COLUMN "LogOnStartDate" TYPE TEXT USING to_char("LogOnStartDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "LogOnEndDate" TYPE TEXT USING to_char("LogOnEndDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "BrokeringDate" TYPE TEXT USING to_char("BrokeringDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "DisconnectDate" TYPE TEXT USING to_char("DisconnectDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "VMStartStartDate" TYPE TEXT USING to_char("VMStartStartDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "VMStartEndDate" TYPE TEXT USING to_char("VMStartEndDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "ClientSessionValidateDate" TYPE TEXT USING to_char("ClientSessionValidateDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "ServerSessionValidateDate" TYPE TEXT USING to_char("ServerSessionValidateDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "EstablishmentDate" TYPE TEXT USING to_char("EstablishmentDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "HdxStartDate" TYPE TEXT USING to_char("HdxStartDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "HdxEndDate" TYPE TEXT USING to_char("HdxEndDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "GpoStartDate" TYPE TEXT USING to_char("GpoStartDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "GpoEndDate" TYPE TEXT USING to_char("GpoEndDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "LogOnScriptsStartDate" TYPE TEXT USING to_char("LogOnScriptsStartDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "LogOnScriptsEndDate" TYPE TEXT USING to_char("LogOnScriptsEndDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "ProfileLoadStartDate" TYPE TEXT USING to_char("ProfileLoadStartDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "ProfileLoadEndDate" TYPE TEXT USING to_char("ProfileLoadEndDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "InteractiveStartDate" TYPE TEXT USING to_char("InteractiveStartDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "InteractiveEndDate" TYPE TEXT USING to_char("InteractiveEndDate", 'YYYY-MM-DD HH24:MI:SS.US'),
    ALTER COLUMN "CreatedDate" TYPE TEXT USING to_char("CreatedDate", 'YYYY-MM-DD HH24:MI:SS.US');

COMMIT;
