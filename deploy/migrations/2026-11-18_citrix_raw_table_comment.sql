-- Citrix RAW 表註解改為「Citrix <站台><資料>（來源：…）」
--
-- 執行於 raw_cda_prod。只改表註解，與各 create_table.py 的 TABLE_COMMENT 一致。

BEGIN;

COMMENT ON TABLE citrix.administration_application IS 'Citrix 行政系統應用程式清單（來源：CitrixFCU01Monitoring.MonitorData.Application）';
COMMENT ON TABLE citrix.administration_application_launch IS 'Citrix 行政系統應用程式啟動紀錄（來源：CitrixFCU01Monitoring.MonitorData.ApplicationInstance）';
COMMENT ON TABLE citrix.administration_session IS 'Citrix 行政系統工作階段紀錄（來源：CitrixFCU01Monitoring.MonitorData.Session）';
COMMENT ON TABLE citrix.administration_user_account IS 'Citrix 行政系統使用者清單（來源：CitrixFCU01Monitoring.MonitorData.User）';
COMMENT ON TABLE citrix.administration_connection IS 'Citrix 行政系統連線紀錄（來源：CitrixFCU01Monitoring.MonitorData.Connection）';

COMMENT ON TABLE citrix.statistics_computing_application IS 'Citrix 統計與數值計算軟體應用程式清單（來源：CitrixFCU02Monitoring.MonitorData.Application）';
COMMENT ON TABLE citrix.statistics_computing_application_launch IS 'Citrix 統計與數值計算軟體應用程式啟動紀錄（來源：CitrixFCU02Monitoring.MonitorData.ApplicationInstance）';
COMMENT ON TABLE citrix.statistics_computing_session IS 'Citrix 統計與數值計算軟體工作階段紀錄（來源：CitrixFCU02Monitoring.MonitorData.Session）';
COMMENT ON TABLE citrix.statistics_computing_user_account IS 'Citrix 統計與數值計算軟體使用者清單（來源：CitrixFCU02Monitoring.MonitorData.User）';
COMMENT ON TABLE citrix.statistics_computing_connection IS 'Citrix 統計與數值計算軟體連線紀錄（來源：CitrixFCU02Monitoring.MonitorData.Connection）';

COMMENT ON TABLE citrix.design_engineering_application IS 'Citrix 設計與工程軟體應用程式清單（來源：CitrixFCUVDIMonitoring1.MonitorData.Application）';
COMMENT ON TABLE citrix.design_engineering_application_launch IS 'Citrix 設計與工程軟體應用程式啟動紀錄（來源：CitrixFCUVDIMonitoring1.MonitorData.ApplicationInstance）';
COMMENT ON TABLE citrix.design_engineering_session IS 'Citrix 設計與工程軟體工作階段紀錄（來源：CitrixFCUVDIMonitoring1.MonitorData.Session）';
COMMENT ON TABLE citrix.design_engineering_user_account IS 'Citrix 設計與工程軟體使用者清單（來源：CitrixFCUVDIMonitoring1.MonitorData.User）';
COMMENT ON TABLE citrix.design_engineering_connection IS 'Citrix 設計與工程軟體連線紀錄（來源：CitrixFCUVDIMonitoring1.MonitorData.Connection）';

COMMIT;
