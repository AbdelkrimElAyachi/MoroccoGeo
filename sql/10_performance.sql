-- =============================================================
-- Morocco Drought & Water Security Observatory
-- Phase 3 - Script 10: performance (columnstore indexes)
-- Run in SSMS after scripts 01-09. Safe to run more than once.
--
-- Columnstore = data stored column by column and compressed: analytical queries
-- ("average rain per region per year") read only the needed columns and run much faster.
-- Non-clustered columnstore indexes are used so the primary keys (row lookups, MERGE loads)
-- stay as they are.
--
-- Partitioning by year (planned in Step 12) is NOT used on purpose: the largest table has about
-- 1 million rows (daily weather); partitioning helps from tens of millions of rows and would only
-- add complexity here.
-- =============================================================
USE DWH_DB;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'NCCI_FactWeatherDaily')
    CREATE NONCLUSTERED COLUMNSTORE INDEX NCCI_FactWeatherDaily
        ON dbo.FactWeatherDaily (DateKey, GeographyKey, TmaxC, TminC, PrecipMm, Et0Mm);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'NCCI_FactDroughtIndex')
    CREATE NONCLUSTERED COLUMNSTORE INDEX NCCI_FactDroughtIndex
        ON dbo.FactDroughtIndex (DateKey, GeographyKey, SpiScale, SpiValue, DroughtCategoryKey);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'NCCI_FactRainfallMonthly')
    CREATE NONCLUSTERED COLUMNSTORE INDEX NCCI_FactRainfallMonthly
        ON dbo.FactRainfallMonthly (DateKey, GeographyKey, RainMm, NormalMm, AnomalyPct);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'NCCI_FactVegetationMonthly')
    CREATE NONCLUSTERED COLUMNSTORE INDEX NCCI_FactVegetationMonthly
        ON dbo.FactVegetationMonthly (DateKey, GeographyKey, NdviCrop, NdviAll, CropSharePct,
                                      NdviCropNormal, NdviCropAnomaly, NdviAllNormal, NdviAllAnomaly);
GO

SELECT OBJECT_NAME(object_id) AS TableName, name AS IndexName, type_desc
FROM sys.indexes WHERE type_desc LIKE '%COLUMNSTORE%' ORDER BY 1;
