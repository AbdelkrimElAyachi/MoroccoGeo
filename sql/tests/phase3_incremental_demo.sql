-- =============================================================
-- Phase 3 demo: an incremental load only adds the new month.
-- Simulates "October 2026 arrives": removes October 2026 from FactRainfallMonthly, then runs the
-- normal load procedure from staging (which still holds all months).
-- Expected receipt: 75 inserted (October 2026 x 75 provinces), 0 updated, the rest unchanged.
-- Safe: the month is put back by the load itself.
-- =============================================================
USE DWH_DB;
SET NOCOUNT ON;

DELETE FROM dbo.FactRainfallMonthly WHERE DateKey = 20261001;
SELECT COUNT(*) AS RowsAfterRemovingOct2026 FROM dbo.FactRainfallMonthly;

EXEC dbo.usp_LoadRainfall;

SELECT TOP 1 TableName, SourceRows, RowsInserted, RowsUpdated, RowsUnchanged,
       CASE WHEN RowsInserted = 75 AND RowsUpdated = 0 THEN 'PASS: only the new month was added' ELSE 'FAIL' END AS Result
FROM etl.LoadAudit WHERE TableName = N'dbo.FactRainfallMonthly' ORDER BY AuditID DESC;

-- Run the same load again: nothing left to add, so the receipt must say 0 inserted, 0 updated.
-- (This also leaves "latest load = no change", which phase3_tests.sql checks.)
EXEC dbo.usp_LoadRainfall;

SELECT TOP 1 TableName, SourceRows, RowsInserted, RowsUpdated, RowsUnchanged,
       CASE WHEN RowsInserted = 0 AND RowsUpdated = 0 THEN 'PASS: re-run after the new month changed nothing' ELSE 'FAIL' END AS Result
FROM etl.LoadAudit WHERE TableName = N'dbo.FactRainfallMonthly' ORDER BY AuditID DESC;
