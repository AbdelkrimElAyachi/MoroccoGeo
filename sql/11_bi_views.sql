-- =============================================================
-- Morocco Drought & Water Security Observatory
-- Phase 4 - Script 11: the "bi" view layer read by the SSAS model, and SSAS read access
-- Run in SSMS. Safe to run more than once.
--
-- Why views: the model reads stable, tidy views instead of the raw tables. If a table changes
-- later, only the view is adapted; the model and dashboards keep working.
-- =============================================================
USE DWH_DB;
GO
IF SCHEMA_ID('bi') IS NULL EXEC('CREATE SCHEMA bi');
GO

-- ---------- Dimensions ----------
CREATE OR ALTER VIEW bi.DimDate AS
SELECT DateKey, [Date], [Year], [Quarter], [Month], MonthNameFr, MonthNameAr, YearMonth, MonthStart,
       [Day], DayNameFr, IsWeekend, AgriSeason, AgriSeasonStartYear, AgriSeasonMonthNo, IsRamadan
FROM dbo.DimDate
WHERE [Year] BETWEEN 1990 AND 2030;     -- the model does not need 1940-1989 (no fact uses them)
GO

CREATE OR ALTER VIEW bi.DimGeography AS
SELECT GeographyKey, GeoLevel, HcpCode, ProvinceName, ProvinceShort, ProvinceType,
       RegionCode, RegionName, ShapeID, AreaKm2, PointLat, PointLon,
       Pop2024, PopUrban2024, PopRural2024, RuralSharePct
FROM dbo.DimGeography;
GO

CREATE OR ALTER VIEW bi.DimCrop AS
SELECT CropKey, FaoItemCode, CropNameEn, CropNameFr, CropGroup, IsAggregate, IsKeyCrop FROM dbo.DimCrop;
GO

CREATE OR ALTER VIEW bi.DimDam AS
SELECT DamKey, DamName, GeographyKey, OsmAreaKm2, MaxWaterKm2, Lat, Lon FROM dbo.DimDam;
GO

CREATE OR ALTER VIEW bi.DimDroughtCategory AS
SELECT DroughtCategoryKey, CategoryFr, CategoryEn, MinSpi, MaxSpi, IsDrought, ColorHex FROM dbo.DimDroughtCategory;
GO

-- ---------- Facts ----------
CREATE OR ALTER VIEW bi.FactRainfall AS
SELECT DateKey, GeographyKey, RainMm, NormalMm, AnomalyPct FROM dbo.FactRainfallMonthly;
GO
CREATE OR ALTER VIEW bi.FactDrought AS
SELECT DateKey, GeographyKey, SpiScale, SpiValue, DroughtCategoryKey FROM dbo.FactDroughtIndex;
GO
CREATE OR ALTER VIEW bi.FactVegetation AS
SELECT DateKey, GeographyKey, NdviCrop, NdviAll, CropSharePct, NdviCropNormal, NdviCropAnomaly,
       NdviAllNormal, NdviAllAnomaly
FROM dbo.FactVegetationMonthly;
GO
CREATE OR ALTER VIEW bi.FactReservoir AS
SELECT DateKey, DamKey, WaterKm2, ClearPct, IsReliable, FillIndexPct FROM dbo.FactReservoirMonthly;
GO
CREATE OR ALTER VIEW bi.FactCropProduction AS
SELECT DateKey, GeographyKey, CropKey, [Year], AreaHa, YieldKgHa, ProductionT FROM dbo.FactCropProduction;
GO
CREATE OR ALTER VIEW bi.FactWeather AS
SELECT DateKey, GeographyKey, TmaxC, TminC, PrecipMm, Et0Mm FROM dbo.FactWeatherDaily;
GO

-- ---------- Read access for Analysis Services ----------
-- SSAS reads the data with its own Windows service account. It gets read-only access
-- (db_datareader) to DWH_DB and nothing else.
USE master;
GO
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'NT Service\MSSQLServerOLAPService')
    CREATE LOGIN [NT Service\MSSQLServerOLAPService] FROM WINDOWS;
GO
USE DWH_DB;
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'NT Service\MSSQLServerOLAPService')
    CREATE USER [NT Service\MSSQLServerOLAPService] FOR LOGIN [NT Service\MSSQLServerOLAPService];
ALTER ROLE db_datareader ADD MEMBER [NT Service\MSSQLServerOLAPService];
GO

SELECT s.name + '.' + v.name AS ViewName FROM sys.views v JOIN sys.schemas s ON s.schema_id = v.schema_id
WHERE s.name = 'bi' ORDER BY v.name;
