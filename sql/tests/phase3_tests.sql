-- =============================================================
-- Phase 3 tests: a clean, reliable warehouse. Every line should show Result = PASS.
-- The last test needs ssis/tests/run_rerun_check.ps1 to have been run.
-- =============================================================
USE DWH_DB;
SET NOCOUNT ON;
DECLARE @t TABLE (TestName NVARCHAR(200), Expected NVARCHAR(60), Actual NVARCHAR(60));

-- 1. Relationships: every foreign key active and trusted
INSERT @t SELECT N'Foreign keys disabled or not trusted', N'0',
    CAST((SELECT COUNT(*) FROM sys.foreign_keys WHERE is_disabled = 1 OR is_not_trusted = 1) AS NVARCHAR(60));
INSERT @t SELECT N'Foreign keys defined (facts -> dimensions)', N'15',
    CAST((SELECT COUNT(*) FROM sys.foreign_keys) AS NVARCHAR(60));

-- 2. Orphans (explicit check, in addition to the foreign keys)
INSERT @t SELECT N'Orphan rows: facts -> DimDate', N'0', CAST((
      (SELECT COUNT(*) FROM dbo.FactRainfallMonthly f   WHERE NOT EXISTS (SELECT 1 FROM dbo.DimDate d WHERE d.DateKey = f.DateKey))
    + (SELECT COUNT(*) FROM dbo.FactDroughtIndex f      WHERE NOT EXISTS (SELECT 1 FROM dbo.DimDate d WHERE d.DateKey = f.DateKey))
    + (SELECT COUNT(*) FROM dbo.FactVegetationMonthly f WHERE NOT EXISTS (SELECT 1 FROM dbo.DimDate d WHERE d.DateKey = f.DateKey))
    + (SELECT COUNT(*) FROM dbo.FactReservoirMonthly f  WHERE NOT EXISTS (SELECT 1 FROM dbo.DimDate d WHERE d.DateKey = f.DateKey))
    + (SELECT COUNT(*) FROM dbo.FactCropProduction f    WHERE NOT EXISTS (SELECT 1 FROM dbo.DimDate d WHERE d.DateKey = f.DateKey))
    + (SELECT COUNT(*) FROM dbo.FactWeatherDaily f      WHERE NOT EXISTS (SELECT 1 FROM dbo.DimDate d WHERE d.DateKey = f.DateKey))) AS NVARCHAR(60));
INSERT @t SELECT N'Orphan rows: facts -> DimGeography', N'0', CAST((
      (SELECT COUNT(*) FROM dbo.FactRainfallMonthly f   WHERE NOT EXISTS (SELECT 1 FROM dbo.DimGeography g WHERE g.GeographyKey = f.GeographyKey))
    + (SELECT COUNT(*) FROM dbo.FactDroughtIndex f      WHERE NOT EXISTS (SELECT 1 FROM dbo.DimGeography g WHERE g.GeographyKey = f.GeographyKey))
    + (SELECT COUNT(*) FROM dbo.FactVegetationMonthly f WHERE NOT EXISTS (SELECT 1 FROM dbo.DimGeography g WHERE g.GeographyKey = f.GeographyKey))
    + (SELECT COUNT(*) FROM dbo.FactCropProduction f    WHERE NOT EXISTS (SELECT 1 FROM dbo.DimGeography g WHERE g.GeographyKey = f.GeographyKey))
    + (SELECT COUNT(*) FROM dbo.FactWeatherDaily f      WHERE NOT EXISTS (SELECT 1 FROM dbo.DimGeography g WHERE g.GeographyKey = f.GeographyKey))) AS NVARCHAR(60));
INSERT @t SELECT N'Orphan rows: reservoirs -> DimDam, SPI -> DimDroughtCategory, crops -> DimCrop', N'0', CAST((
      (SELECT COUNT(*) FROM dbo.FactReservoirMonthly f WHERE NOT EXISTS (SELECT 1 FROM dbo.DimDam d WHERE d.DamKey = f.DamKey))
    + (SELECT COUNT(*) FROM dbo.FactDroughtIndex f     WHERE NOT EXISTS (SELECT 1 FROM dbo.DimDroughtCategory c WHERE c.DroughtCategoryKey = f.DroughtCategoryKey))
    + (SELECT COUNT(*) FROM dbo.FactCropProduction f   WHERE NOT EXISTS (SELECT 1 FROM dbo.DimCrop c WHERE c.CropKey = f.CropKey))) AS NVARCHAR(60));

-- 3. Grain rules
INSERT @t SELECT N'Monthly facts not on the 1st of the month', N'0', CAST((
      (SELECT COUNT(*) FROM dbo.FactRainfallMonthly   WHERE DateKey % 100 <> 1)
    + (SELECT COUNT(*) FROM dbo.FactDroughtIndex      WHERE DateKey % 100 <> 1)
    + (SELECT COUNT(*) FROM dbo.FactVegetationMonthly WHERE DateKey % 100 <> 1)
    + (SELECT COUNT(*) FROM dbo.FactReservoirMonthly  WHERE DateKey % 100 <> 1)) AS NVARCHAR(60));
INSERT @t SELECT N'Yearly crop facts not on 1 January', N'0',
    CAST((SELECT COUNT(*) FROM dbo.FactCropProduction WHERE DateKey % 10000 <> 101) AS NVARCHAR(60));
INSERT @t SELECT N'Province facts pointing to the country row (key 0)', N'0', CAST((
      (SELECT COUNT(*) FROM dbo.FactRainfallMonthly   WHERE GeographyKey = 0)
    + (SELECT COUNT(*) FROM dbo.FactDroughtIndex      WHERE GeographyKey = 0)
    + (SELECT COUNT(*) FROM dbo.FactVegetationMonthly WHERE GeographyKey = 0)) AS NVARCHAR(60));
INSERT @t SELECT N'SPI scales other than 1, 3, 6, 12', N'0',
    CAST((SELECT COUNT(*) FROM dbo.FactDroughtIndex WHERE SpiScale NOT IN (1, 3, 6, 12)) AS NVARCHAR(60));
INSERT @t SELECT N'SPI value outside its category range', N'0',
    CAST((SELECT COUNT(*) FROM dbo.FactDroughtIndex f JOIN dbo.DimDroughtCategory c ON c.DroughtCategoryKey = f.DroughtCategoryKey
          WHERE f.SpiValue < c.MinSpi OR f.SpiValue >= c.MaxSpi) AS NVARCHAR(60));

-- 4. Performance
INSERT @t SELECT N'Columnstore indexes on large facts', N'4',
    CAST((SELECT COUNT(*) FROM sys.indexes WHERE type_desc = 'NONCLUSTERED COLUMNSTORE') AS NVARCHAR(60));

-- 5. Safe re-runs: the latest load of each table changed nothing (after run_rerun_check.ps1)
INSERT @t SELECT N'Latest load per table: rows inserted + updated', N'0',
    CAST((SELECT ISNULL(SUM(RowsInserted + RowsUpdated), -1) FROM (
          SELECT TableName, RowsInserted, RowsUpdated,
                 ROW_NUMBER() OVER (PARTITION BY TableName ORDER BY AuditID DESC) rn
          FROM etl.LoadAudit) x WHERE rn = 1) AS NVARCHAR(60));

SELECT TestName, Expected, Actual, CASE WHEN Expected = Actual THEN 'PASS' ELSE 'FAIL' END AS Result FROM @t;
SELECT CASE WHEN SUM(CASE WHEN Expected = Actual THEN 0 ELSE 1 END) = 0 THEN 'ALL PHASE 3 TESTS PASSED'
            ELSE CAST(SUM(CASE WHEN Expected = Actual THEN 0 ELSE 1 END) AS VARCHAR(10)) + ' TEST(S) FAILED' END AS Summary
FROM @t;
