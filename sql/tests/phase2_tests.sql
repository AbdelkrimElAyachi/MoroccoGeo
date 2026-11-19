-- =============================================================
-- Phase 2 tests (Steps 6-9; Step 7 weather once downloaded).
-- Every line should show Result = PASS. Weather tests show SKIP until the data is loaded.
-- =============================================================
USE DWH_DB;
SET NOCOUNT ON;
DECLARE @t TABLE (Step VARCHAR(10), TestName NVARCHAR(200), Expected NVARCHAR(60), Actual NVARCHAR(60));
DECLARE @wheat INT = (SELECT CropKey FROM dbo.DimCrop WHERE FaoItemCode = 15);

-- ---------- Step 6: crops ----------
INSERT @t SELECT 'Step 6', N'Wheat production 2024 (t, FAOSTAT)', N'2441670',
    CAST((SELECT CAST(ROUND(ProductionT, 0) AS BIGINT) FROM dbo.FactCropProduction WHERE CropKey = @wheat AND [Year] = 2024) AS NVARCHAR(60));
INSERT @t SELECT 'Step 6', N'Wheat production 2021 (t, FAOSTAT)', N'7543848',
    CAST((SELECT CAST(ROUND(ProductionT, 0) AS BIGINT) FROM dbo.FactCropProduction WHERE CropKey = @wheat AND [Year] = 2021) AS NVARCHAR(60));
INSERT @t SELECT 'Step 6', N'Wheat years 2000-2024', N'25',
    CAST((SELECT COUNT(*) FROM dbo.FactCropProduction WHERE CropKey = @wheat AND [Year] BETWEEN 2000 AND 2024) AS NVARCHAR(60));
INSERT @t SELECT 'Step 6', N'Harvest 2024 linked to season 2023-24', N'2023-24',
    (SELECT TOP 1 d.AgriSeason FROM dbo.FactCropProduction f JOIN dbo.DimDate d ON d.DateKey = f.DateKey WHERE f.[Year] = 2024);
INSERT @t SELECT 'Step 6', N'Key crops flagged', N'10',
    CAST((SELECT COUNT(*) FROM dbo.DimCrop WHERE IsKeyCrop = 1) AS NVARCHAR(60));

-- ---------- Step 8: rainfall ----------
DECLARE @months INT = (SELECT DATEDIFF(MONTH, '1991-01-01', MAX(d.[Date])) + 1
                       FROM dbo.FactRainfallMonthly f JOIN dbo.DimDate d ON d.DateKey = f.DateKey);
INSERT @t SELECT 'Step 8', N'Rows = 75 provinces x months since 1991-01', CAST(75 * @months AS NVARCHAR(60)),
    CAST((SELECT COUNT(*) FROM dbo.FactRainfallMonthly) AS NVARCHAR(60));
INSERT @t SELECT 'Step 8', N'Provinces with rainfall', N'75',
    CAST((SELECT COUNT(DISTINCT GeographyKey) FROM dbo.FactRainfallMonthly) AS NVARCHAR(60));
INSERT @t SELECT 'Step 8', N'Negative rainfall values', N'0',
    CAST((SELECT COUNT(*) FROM dbo.FactRainfallMonthly WHERE RainMm < 0) AS NVARCHAR(60));
INSERT @t SELECT 'Step 8', N'Rows without 1991-2020 normal', N'0',
    CAST((SELECT COUNT(*) FROM dbo.FactRainfallMonthly WHERE NormalMm IS NULL) AS NVARCHAR(60));
INSERT @t SELECT 'Step 8', N'July is dry: national mean July rain < 10 mm', N'1',
    CAST((SELECT CASE WHEN AVG(f.RainMm) < 10 THEN 1 ELSE 0 END FROM dbo.FactRainfallMonthly f
          JOIN dbo.DimDate d ON d.DateKey = f.DateKey WHERE d.[Month] = 7) AS NVARCHAR(60));
INSERT @t SELECT 'Step 8', N'Wet north: Chefchaouen normal annual rain > 500 mm', N'1',
    CAST((SELECT CASE WHEN SUM(x.n) > 500 THEN 1 ELSE 0 END FROM (
          SELECT DISTINCT d.[Month], f.NormalMm AS n FROM dbo.FactRainfallMonthly f
          JOIN dbo.DimDate d ON d.DateKey = f.DateKey JOIN dbo.DimGeography g ON g.GeographyKey = f.GeographyKey
          WHERE g.ProvinceShort = N'Chefchaouen') x) AS NVARCHAR(60));
INSERT @t SELECT 'Step 8', N'Dry south: Aousserd normal annual rain < 100 mm', N'1',
    CAST((SELECT CASE WHEN SUM(x.n) < 100 THEN 1 ELSE 0 END FROM (
          SELECT DISTINCT d.[Month], f.NormalMm AS n FROM dbo.FactRainfallMonthly f
          JOIN dbo.DimDate d ON d.DateKey = f.DateKey JOIN dbo.DimGeography g ON g.GeographyKey = f.GeographyKey
          WHERE g.ProvinceShort = N'Aousserd') x) AS NVARCHAR(60));

-- ---------- Step 9: SPI ----------
INSERT @t SELECT 'Step 9', N'SPI-12 mean over 1991-2020 within +/-0.1', N'1',
    CAST((SELECT CASE WHEN ABS(AVG(SpiValue)) <= 0.1 THEN 1 ELSE 0 END FROM dbo.FactDroughtIndex f
          JOIN dbo.DimDate d ON d.DateKey = f.DateKey WHERE f.SpiScale = 12 AND d.[Year] BETWEEN 1991 AND 2020) AS NVARCHAR(60));
INSERT @t SELECT 'Step 9', N'SPI-12 std over 1991-2020 between 0.9 and 1.1', N'1',
    CAST((SELECT CASE WHEN STDEV(SpiValue) BETWEEN 0.9 AND 1.1 THEN 1 ELSE 0 END FROM dbo.FactDroughtIndex f
          JOIN dbo.DimDate d ON d.DateKey = f.DateKey WHERE f.SpiScale = 12 AND d.[Year] BETWEEN 1991 AND 2020) AS NVARCHAR(60));
INSERT @t
SELECT 'Step 9', N'Season ' + s.Season + N' national SPI-12 (August) ' + s.Sign, N'1',
    CAST((SELECT CASE WHEN (s.Sign = N'< -0.5' AND AVG(f.SpiValue) < -0.5) OR (s.Sign = N'> 0.5' AND AVG(f.SpiValue) > 0.5)
                      THEN 1 ELSE 0 END
          FROM dbo.FactDroughtIndex f WHERE f.SpiScale = 12 AND f.DateKey = s.AugKey) AS NVARCHAR(60))
FROM (VALUES (N'1994-95', 19950801, N'< -0.5'), (N'2021-22', 20220801, N'< -0.5'),
             (N'2023-24', 20240801, N'< -0.5'), (N'2009-10', 20100801, N'> 0.5')) s(Season, AugKey, Sign);
INSERT @t SELECT 'Step 9', N'SPI rows with a drought category', N'100%',
    CAST(CAST(100.0 * SUM(CASE WHEN DroughtCategoryKey IS NOT NULL THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS INT) AS NVARCHAR(10)) + N'%'
    FROM dbo.FactDroughtIndex;

-- ---------- Step 11: reservoirs ----------
IF EXISTS (SELECT 1 FROM dbo.FactReservoirMonthly)
BEGIN
    DECLARE @massira INT = (SELECT DamKey FROM dbo.DimDam WHERE DamName = N'Barrage Al Massira');
    INSERT @t SELECT 'Step 11', N'Reservoirs (OpenStreetMap, >= 4 km2)', N'26', CAST((SELECT COUNT(*) FROM dbo.DimDam) AS NVARCHAR(60));
    INSERT @t SELECT 'Step 11', N'Rows = dams x months', CAST((SELECT COUNT(*) FROM dbo.DimDam) * (SELECT COUNT(DISTINCT DateKey) FROM dbo.FactReservoirMonthly) AS NVARCHAR(60)),
        CAST((SELECT COUNT(*) FROM dbo.FactReservoirMonthly) AS NVARCHAR(60));
    INSERT @t SELECT 'Step 11', N'Reliable months (>= 80 % clear) >= 95 %', N'1',
        CAST((SELECT CASE WHEN AVG(CAST(IsReliable AS FLOAT)) >= 0.95 THEN 1 ELSE 0 END FROM dbo.FactReservoirMonthly) AS NVARCHAR(60));
    INSERT @t SELECT 'Step 11', N'Al Massira fill April 2024 < 30 % (drought)', N'1',
        CAST((SELECT CASE WHEN FillIndexPct < 30 THEN 1 ELSE 0 END FROM dbo.FactReservoirMonthly WHERE DamKey = @massira AND DateKey = 20240401) AS NVARCHAR(60));
    INSERT @t SELECT 'Step 11', N'Al Massira fill April 2026 > 80 % (recovery)', N'1',
        CAST((SELECT CASE WHEN FillIndexPct > 80 THEN 1 ELSE 0 END FROM dbo.FactReservoirMonthly WHERE DamKey = @massira AND DateKey = 20260401) AS NVARCHAR(60));
    INSERT @t SELECT 'Step 11', N'Satellite index follows official order: Feb 2024 < Jan 2026 < May 2026', N'1',
        CAST((SELECT CASE WHEN a < b AND b < c THEN 1 ELSE 0 END FROM (
              SELECT SUM(CASE WHEN f.DateKey = 20240201 THEN f.WaterKm2 END) / SUM(CASE WHEN f.DateKey = 20240201 THEN d.MaxWaterKm2 END) a,
                     SUM(CASE WHEN f.DateKey = 20260101 THEN f.WaterKm2 END) / SUM(CASE WHEN f.DateKey = 20260101 THEN d.MaxWaterKm2 END) b,
                     SUM(CASE WHEN f.DateKey = 20260501 THEN f.WaterKm2 END) / SUM(CASE WHEN f.DateKey = 20260501 THEN d.MaxWaterKm2 END) c
              FROM dbo.FactReservoirMonthly f JOIN dbo.DimDam d ON d.DamKey = f.DamKey) x) AS NVARCHAR(60));
END
ELSE INSERT @t SELECT 'Step 11', N'Reservoirs loaded', N'SKIP', N'SKIP';

-- ---------- Step 10: vegetation ----------
IF EXISTS (SELECT 1 FROM dbo.FactVegetationMonthly)
BEGIN
    DECLARE @settat INT = (SELECT GeographyKey FROM dbo.DimGeography WHERE ProvinceShort = N'Settat');
    INSERT @t SELECT 'Step 10', N'Rows = 75 provinces x months', CAST(75 * (SELECT COUNT(DISTINCT DateKey) FROM dbo.FactVegetationMonthly) AS NVARCHAR(60)),
        CAST((SELECT COUNT(*) FROM dbo.FactVegetationMonthly) AS NVARCHAR(60));
    INSERT @t SELECT 'Step 10', N'NDVI values outside -0.2..1', N'0',
        CAST((SELECT COUNT(*) FROM dbo.FactVegetationMonthly WHERE NdviAll NOT BETWEEN -0.2 AND 1 OR NdviCrop NOT BETWEEN -0.2 AND 1) AS NVARCHAR(60));
    INSERT @t SELECT 'Step 10', N'Settat farmland greener in March than August (normal)', N'1',
        CAST((SELECT CASE WHEN MAX(CASE WHEN d.[Month] = 3 THEN f.NdviCropNormal END) > MAX(CASE WHEN d.[Month] = 8 THEN f.NdviCropNormal END) THEN 1 ELSE 0 END
              FROM dbo.FactVegetationMonthly f JOIN dbo.DimDate d ON d.DateKey = f.DateKey WHERE f.GeographyKey = @settat) AS NVARCHAR(60));
    INSERT @t SELECT 'Step 10', N'Settat March 2021 (good harvest) greener than March 2024 (drought)', N'1',
        CAST((SELECT CASE WHEN MAX(CASE WHEN DateKey = 20210301 THEN NdviCrop END) > MAX(CASE WHEN DateKey = 20240301 THEN NdviCrop END) THEN 1 ELSE 0 END
              FROM dbo.FactVegetationMonthly WHERE GeographyKey = @settat) AS NVARCHAR(60));
END
ELSE INSERT @t SELECT 'Step 10', N'Vegetation loaded', N'SKIP', N'SKIP';

-- ---------- Step 7: weather (SKIP until loaded) ----------
IF EXISTS (SELECT 1 FROM dbo.FactWeatherDaily)
BEGIN
    INSERT @t SELECT 'Step 7', N'Provinces with weather', N'75',
        CAST((SELECT COUNT(DISTINCT GeographyKey) FROM dbo.FactWeatherDaily) AS NVARCHAR(60));
    INSERT @t SELECT 'Step 7', N'Same number of days for every province', N'1',
        CAST((SELECT CASE WHEN MIN(n) = MAX(n) THEN 1 ELSE 0 END FROM
              (SELECT COUNT(*) n FROM dbo.FactWeatherDaily GROUP BY GeographyKey) x) AS NVARCHAR(60));
    INSERT @t SELECT 'Step 7', N'Tmax outside -15..55 C', N'0',
        CAST((SELECT COUNT(*) FROM dbo.FactWeatherDaily WHERE TmaxC NOT BETWEEN -15 AND 55) AS NVARCHAR(60));
    INSERT @t SELECT 'Step 7', N'Starts 1991-01-01', N'19910101',
        CAST((SELECT MIN(DateKey) FROM dbo.FactWeatherDaily) AS NVARCHAR(60));
END
ELSE
    INSERT @t SELECT 'Step 7', N'Weather loaded', N'SKIP', N'SKIP';

SELECT Step, TestName, Expected, Actual,
       CASE WHEN Expected = 'SKIP' THEN 'SKIP' WHEN Expected = Actual THEN 'PASS' ELSE 'FAIL' END AS Result
FROM @t;
SELECT CASE WHEN SUM(CASE WHEN Expected NOT IN ('SKIP') AND (Actual IS NULL OR Expected <> Actual) THEN 1 ELSE 0 END) = 0
            THEN 'ALL PHASE 2 TESTS PASSED' + CASE WHEN EXISTS (SELECT 1 FROM @t WHERE Expected = 'SKIP') THEN ' (some steps skipped: not loaded yet)' ELSE '' END
            ELSE CAST(SUM(CASE WHEN Expected NOT IN ('SKIP') AND (Actual IS NULL OR Expected <> Actual) THEN 1 ELSE 0 END) AS VARCHAR(10)) + ' TEST(S) FAILED' END AS Summary
FROM @t;
