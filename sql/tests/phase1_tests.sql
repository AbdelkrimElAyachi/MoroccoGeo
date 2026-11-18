-- =============================================================
-- Phase 1 tests (Steps 3, 4, 5). Every line should show Result = PASS.
-- Run in SSMS after the packages 01_Boundaries and 02_Geography and sql/06_dim_date.sql.
-- =============================================================
SET NOCOUNT ON;
DECLARE @t TABLE (Step VARCHAR(10), TestName NVARCHAR(200), Expected NVARCHAR(100), Actual NVARCHAR(100));

-- ---------- Step 3: boundaries ----------
INSERT @t SELECT 'Step 3', N'Provinces in stg.Boundaries', N'75',
       CAST((SELECT COUNT(*) FROM Staging_DB.stg.Boundaries) AS NVARCHAR(100));
INSERT @t SELECT 'Step 3', N'Duplicate shape IDs', N'0',
       CAST((SELECT COUNT(*) - COUNT(DISTINCT shape_id) FROM Staging_DB.stg.Boundaries) AS NVARCHAR(100));
INSERT @t SELECT 'Step 3', N'Southern provinces present (Aousserd, Oued Ed-Dahab, Laayoune, Boujdour, Es-Semara, Tarfaya)', N'6',
       CAST((SELECT COUNT(*) FROM Staging_DB.stg.Boundaries
             WHERE shape_name LIKE N'%Aousserd%' OR shape_name LIKE N'%Oued Ed-Dahab%' OR shape_name LIKE N'%Laayoune%'
                OR shape_name LIKE N'%Boujdour%' OR shape_name LIKE N'%Semara%' OR shape_name LIKE N'%Tarfaya%') AS NVARCHAR(100));

-- ---------- Step 4: DimGeography ----------
INSERT @t SELECT 'Step 4', N'Reviewed mappings', N'75', CAST((SELECT COUNT(*) FROM DWH_DB.dbo.MapProvince) AS NVARCHAR(100));
INSERT @t SELECT 'Step 4', N'Province rows', N'75',
       CAST((SELECT COUNT(*) FROM DWH_DB.dbo.DimGeography WHERE GeoLevel = 'Province') AS NVARCHAR(100));
INSERT @t SELECT 'Step 4', N'Regions', N'12',
       CAST((SELECT COUNT(DISTINCT RegionCode) FROM DWH_DB.dbo.DimGeography WHERE GeoLevel = 'Province') AS NVARCHAR(100));
INSERT @t SELECT 'Step 4', N'Total population 2024 (HCP)', N'36828330',
       CAST((SELECT SUM(Pop2024) FROM DWH_DB.dbo.DimGeography WHERE GeoLevel = 'Province') AS NVARCHAR(100));
INSERT @t SELECT 'Step 4', N'Country row (key 0) population', N'36828330',
       CAST((SELECT Pop2024 FROM DWH_DB.dbo.DimGeography WHERE GeographyKey = 0) AS NVARCHAR(100));
INSERT @t SELECT 'Step 4', N'Settat population (HCP Excel)', N'652292',
       CAST((SELECT Pop2024 FROM DWH_DB.dbo.DimGeography WHERE ProvinceShort = N'Settat') AS NVARCHAR(100));
INSERT @t SELECT 'Step 4', N'Ifrane population (HCP Excel)', N'160904',
       CAST((SELECT Pop2024 FROM DWH_DB.dbo.DimGeography WHERE ProvinceShort = N'Ifrane') AS NVARCHAR(100));
INSERT @t SELECT 'Step 4', N'Al Haouz population (HCP Excel)', N'642815',
       CAST((SELECT Pop2024 FROM DWH_DB.dbo.DimGeography WHERE ProvinceShort = N'Al Haouz') AS NVARCHAR(100));
INSERT @t SELECT 'Step 4', N'Provinces without outline or inside point', N'0',
       CAST((SELECT COUNT(*) FROM DWH_DB.dbo.DimGeography
             WHERE GeoLevel = 'Province' AND (ShapeID IS NULL OR PointLat IS NULL)) AS NVARCHAR(100));
INSERT @t SELECT 'Step 4', N'Urban + rural = total (rows that differ)', N'0',
       CAST((SELECT COUNT(*) FROM DWH_DB.dbo.DimGeography WHERE PopUrban2024 + PopRural2024 <> Pop2024) AS NVARCHAR(100));

-- ---------- Step 5: DimDate ----------
INSERT @t SELECT 'Step 5', N'Days 1940-01-01 .. 2030-12-31', N'33238',
       CAST((SELECT COUNT(*) FROM DWH_DB.dbo.DimDate) AS NVARCHAR(100));
INSERT @t SELECT 'Step 5', N'Gaps (days expected - days present)', N'0',
       CAST((SELECT DATEDIFF(DAY, MIN([Date]), MAX([Date])) + 1 - COUNT(*) FROM DWH_DB.dbo.DimDate) AS NVARCHAR(100));
INSERT @t SELECT 'Step 5', N'Season of 2024-03-15', N'2023-24',
       (SELECT AgriSeason FROM DWH_DB.dbo.DimDate WHERE [Date] = '2024-03-15');
INSERT @t SELECT 'Step 5', N'Season of 2024-10-01', N'2024-25',
       (SELECT AgriSeason FROM DWH_DB.dbo.DimDate WHERE [Date] = '2024-10-01');
INSERT @t SELECT 'Step 5', N'Weekday of 2024-03-15', N'Vendredi',
       (SELECT DayNameFr FROM DWH_DB.dbo.DimDate WHERE [Date] = '2024-03-15');
INSERT @t SELECT 'Step 5', N'Ramadan 2024 starts on 11 or 12 March (Morocco: 12 March)', N'1',
       CAST((SELECT CASE WHEN MIN([Date]) IN ('2024-03-11', '2024-03-12') THEN 1 ELSE 0 END
             FROM DWH_DB.dbo.DimDate WHERE IsRamadan = 1 AND [Year] = 2024) AS NVARCHAR(100));
INSERT @t SELECT 'Step 5', N'Ramadan 2024 length is 29 or 30 days', N'1',
       CAST((SELECT CASE WHEN COUNT(*) IN (29, 30) THEN 1 ELSE 0 END
             FROM DWH_DB.dbo.DimDate WHERE IsRamadan = 1 AND [Year] = 2024) AS NVARCHAR(100));

SELECT Step, TestName, Expected, Actual,
       CASE WHEN Expected = Actual THEN 'PASS' ELSE 'FAIL' END AS Result
FROM @t;

SELECT CASE WHEN SUM(CASE WHEN Expected = Actual THEN 0 ELSE 1 END) = 0
            THEN 'ALL PHASE 1 TESTS PASSED'
            ELSE CAST(SUM(CASE WHEN Expected = Actual THEN 0 ELSE 1 END) AS VARCHAR(10)) + ' TEST(S) FAILED' END AS Summary
FROM @t;
