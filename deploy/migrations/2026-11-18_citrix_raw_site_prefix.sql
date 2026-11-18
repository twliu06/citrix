-- 統計與數值計算軟體站台（CitrixFCU02Monitoring）的 RAW 表加上站台前綴
--
-- 執行於 raw_cda_prod。只改名稱與註解，資料、id 與序號都不動。
-- 另外兩個站台的 RAW 表由 create_table.py 新建，不在本檔。
-- 索引名稱一併改為 uk_<表>_<欄位>、idx_<表>_<欄位>；主鍵與序號改成新表名的預設名稱，
-- 與新建的兩個站台一致。

BEGIN;

-- application → statistics_computing_application
ALTER TABLE citrix.application RENAME TO statistics_computing_application;
ALTER TABLE citrix.statistics_computing_application RENAME CONSTRAINT application_pkey TO statistics_computing_application_pkey;
ALTER SEQUENCE citrix.application_id_seq RENAME TO statistics_computing_application_id_seq;
ALTER INDEX citrix.uq_application_key RENAME TO uk_statistics_computing_application_id;
ALTER INDEX citrix.idx_application_modified RENAME TO idx_statistics_computing_application_modified_date;
COMMENT ON TABLE citrix.statistics_computing_application IS '應用程式清單，統計與數值計算軟體站台（來源：CitrixFCU02Monitoring.MonitorData.Application）';

-- application_launch → statistics_computing_application_launch
ALTER TABLE citrix.application_launch RENAME TO statistics_computing_application_launch;
ALTER TABLE citrix.statistics_computing_application_launch RENAME CONSTRAINT application_launch_pkey TO statistics_computing_application_launch_pkey;
ALTER SEQUENCE citrix.application_launch_id_seq RENAME TO statistics_computing_application_launch_id_seq;
ALTER INDEX citrix.uq_application_launch_key RENAME TO uk_statistics_computing_application_launch_id;
ALTER INDEX citrix.idx_application_launch_modified RENAME TO idx_statistics_computing_application_launch_modified_date;
COMMENT ON TABLE citrix.statistics_computing_application_launch IS '應用程式啟動紀錄，統計與數值計算軟體站台（來源：CitrixFCU02Monitoring.MonitorData.ApplicationInstance）';

-- session → statistics_computing_session
ALTER TABLE citrix.session RENAME TO statistics_computing_session;
ALTER TABLE citrix.statistics_computing_session RENAME CONSTRAINT session_pkey TO statistics_computing_session_pkey;
ALTER SEQUENCE citrix.session_id_seq RENAME TO statistics_computing_session_id_seq;
ALTER INDEX citrix.uq_session_key RENAME TO uk_statistics_computing_session_session_key;
ALTER INDEX citrix.idx_session_modified RENAME TO idx_statistics_computing_session_modified_date;
COMMENT ON TABLE citrix.statistics_computing_session IS '工作階段紀錄，統計與數值計算軟體站台（來源：CitrixFCU02Monitoring.MonitorData.Session）';

-- user_account → statistics_computing_user_account
ALTER TABLE citrix.user_account RENAME TO statistics_computing_user_account;
ALTER TABLE citrix.statistics_computing_user_account RENAME CONSTRAINT user_account_pkey TO statistics_computing_user_account_pkey;
ALTER SEQUENCE citrix.user_account_id_seq RENAME TO statistics_computing_user_account_id_seq;
ALTER INDEX citrix.uq_user_account_key RENAME TO uk_statistics_computing_user_account_id;
ALTER INDEX citrix.idx_user_account_modified RENAME TO idx_statistics_computing_user_account_modified_date;
COMMENT ON TABLE citrix.statistics_computing_user_account IS '使用者清單，統計與數值計算軟體站台（來源：CitrixFCU02Monitoring.MonitorData.User）';

-- connection → statistics_computing_connection
ALTER TABLE citrix.connection RENAME TO statistics_computing_connection;
ALTER TABLE citrix.statistics_computing_connection RENAME CONSTRAINT connection_pkey TO statistics_computing_connection_pkey;
ALTER SEQUENCE citrix.connection_id_seq RENAME TO statistics_computing_connection_id_seq;
ALTER INDEX citrix.uq_connection_key RENAME TO uk_statistics_computing_connection_id;
ALTER INDEX citrix.idx_connection_modified RENAME TO idx_statistics_computing_connection_modified_date;
COMMENT ON TABLE citrix.statistics_computing_connection IS '連線紀錄，統計與數值計算軟體站台（來源：CitrixFCU02Monitoring.MonitorData.Connection）';

COMMIT;
