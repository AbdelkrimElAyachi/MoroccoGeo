-- =============================================================
-- Tests for the native SSIS components (run in SSMS after running 04_Rainfall_SSIS, 06_Weather_SSIS, 09_Province_Fuzzy)
-- Each line: test name | expected | found | PASS/FAIL
-- =============================================================
SET NOCOUNT ON;
DECLARE @t TABLE (Test NVARCHAR(120), Expected NVARCHAR(40), Found NVARCHAR(40), Result AS (CASE WHEN Expected = Found THEN 'PASS' ELSE 'FAIL' END));

-- A. Rainfall Data Flow: same rows as the CSV, nothing rejected, audit written
INSERT @t (Test, Expected, Found) SELECT N'A1 stg.ChirpsMonthly rows (75 x 430)', '32250', CAST(COUNT(*) AS NVARCHAR(40)) FROM Staging_DB.stg.ChirpsMonthly;
INSERT @t (Test, Expected, Found) SELECT N'A2 rainfall rows rejected', '0', CAST(COUNT(*) AS NVARCHAR(40)) FROM Staging_DB.stg.RejectedRows WHERE PackageName = N'04_Rainfall_SSIS';
INSERT @t (Test, Expected, Found) SELECT N'A3 last rainfall audit: read = loaded + rejected', 'yes',
       ISNULL((SELECT TOP 1 CASE WHEN RowsRead = RowsLoaded + RowsRejected THEN 'yes' ELSE 'no' END
               FROM DWH_DB.etl.DataFlowAudit WHERE PackageName = N'04_Rainfall_SSIS' ORDER BY AuditID DESC), 'no audit yet');
INSERT @t (Test, Expected, Found) SELECT N'A4 FactRainfallMonthly unchanged', '32250', CAST(COUNT(*) AS NVARCHAR(40)) FROM DWH_DB.dbo.FactRainfallMonthly;

-- B. Weather Data Flow
INSERT @t (Test, Expected, Found) SELECT N'B1 stg.WeatherDaily rows (75 x 13,099)', '982425', CAST(COUNT(*) AS NVARCHAR(40)) FROM Staging_DB.stg.WeatherDaily;
INSERT @t (Test, Expected, Found) SELECT N'B2 weather rows rejected', '0', CAST(COUNT(*) AS NVARCHAR(40)) FROM Staging_DB.stg.RejectedRows WHERE PackageName = N'06_Weather_SSIS';
INSERT @t (Test, Expected, Found) SELECT N'B3 last weather audit: read = loaded + rejected', 'yes',
       ISNULL((SELECT TOP 1 CASE WHEN RowsRead = RowsLoaded + RowsRejected THEN 'yes' ELSE 'no' END
               FROM DWH_DB.etl.DataFlowAudit WHERE PackageName = N'06_Weather_SSIS' ORDER BY AuditID DESC), 'no audit yet');

-- C. Fuzzy Lookup: every census province gets a map province, and the same one as the reviewed mapping
INSERT @t (Test, Expected, Found) SELECT N'C1 fuzzy output rows', '75', CAST(COUNT(*) AS NVARCHAR(40)) FROM Staging_DB.stg.ProvinceMatchFuzzy;
INSERT @t (Test, Expected, Found) SELECT N'C2 provinces matched (shape_id not NULL)', '75', CAST(COUNT(shape_id) AS NVARCHAR(40)) FROM Staging_DB.stg.ProvinceMatchFuzzy;
INSERT @t (Test, Expected, Found) SELECT N'C3 same match as the reviewed mapping', '75', CAST(SUM(same_as_reviewed) AS NVARCHAR(40)) FROM DWH_DB.etl.vProvinceFuzzyCheck;

SELECT * FROM @t;
-- Matches that differ from the reviewed mapping (empty when C3 passes):
SELECT province_name, name_clean, geo_name_clean, similarity, confidence, fuzzy_shape_id, reviewed_shape_id
FROM DWH_DB.etl.vProvinceFuzzyCheck WHERE same_as_reviewed = 0 ORDER BY similarity;
