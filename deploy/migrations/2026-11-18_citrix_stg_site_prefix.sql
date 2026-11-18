-- 統計與數值計算軟體站台的 STG 表改名
--
-- 執行於 stg_cda_prod。只改名稱與註解，資料不動。
-- ⚠️ 改名後 Power BI 讀舊表名的報表會讀不到資料，執行前先與報表維護者約好切換時間。
-- 舊表的 idx_ 索引不一定存在，改名用 IF EXISTS；缺的索引由 stg.create_table 補建。

BEGIN;

ALTER TABLE private.citrix_software_usage RENAME TO citrix_statistics_computing_usage;
ALTER TABLE private.citrix_statistics_computing_usage RENAME CONSTRAINT citrix_software_usage_pkey TO citrix_statistics_computing_usage_pkey;
ALTER SEQUENCE private.citrix_software_usage_id_seq RENAME TO citrix_statistics_computing_usage_id_seq;
ALTER INDEX IF EXISTS private.idx_citrix_software_usage_app_started RENAME TO idx_citrix_statistics_computing_usage_app_started_at;
ALTER INDEX IF EXISTS private.idx_citrix_software_usage_user RENAME TO idx_citrix_statistics_computing_usage_user_identifier;
COMMENT ON TABLE private.citrix_statistics_computing_usage IS 'Citrix 統計與數值計算軟體使用紀錄';

COMMIT;
