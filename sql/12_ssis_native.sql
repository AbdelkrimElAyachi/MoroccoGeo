-- =============================================================
-- 12 - Support objects for the native SSIS components (Data Flows, Fuzzy Lookup, exports)
--
-- Staging_DB
--   stg.RejectedRows            rows refused by a Data Flow (Conditional Split / Lookup no match)
--   stg.fn_CleanProvinceName    name cleaning before the Fuzzy Lookup (Arabic part, prefixes, dashes)
--   stg.vHcpProvinceNames       census names, cleaned (Fuzzy Lookup input)
--   stg.GeoProvinceNames        map names, cleaned (Fuzzy Lookup reference table)
--   stg.usp_PrepareGeoNames     refills stg.GeoProvinceNames (run before the Fuzzy Lookup)
--   stg.ProvinceMatchFuzzy      Fuzzy Lookup output
-- DWH_DB
--   etl.DataFlowAudit + etl.usp_LogDataFlow   rows read / rejected / loaded by each Data Flow
--   etl.vProvinceFuzzyCheck     Fuzzy Lookup result vs the reviewed mapping dbo.MapProvince
--   export.*                    the Kaggle tables, read by the export package (Flat File Destinations)
-- Run once in SSMS. Safe to run again.
-- =============================================================
USE Staging_DB;
GO
IF OBJECT_ID('stg.RejectedRows') IS NULL
CREATE TABLE stg.RejectedRows (
    RejectedID   INT IDENTITY(1,1) PRIMARY KEY,
    RejectedAt   DATETIME2(0)  NOT NULL DEFAULT SYSDATETIME(),
    PackageName  NVARCHAR(50)  NOT NULL,
    Reason       NVARCHAR(100) NOT NULL,
    RowKey       NVARCHAR(100) NULL,      -- e.g. month + province ID
    RowValue     NVARCHAR(200) NULL       -- the refused value(s), as text
);
GO

CREATE OR ALTER FUNCTION stg.fn_CleanProvinceName (@name NVARCHAR(200))
RETURNS NVARCHAR(200)
AS
BEGIN
    DECLARE @n NVARCHAR(200) = @name;
    -- 1. cut the Arabic part (geoBoundaries names are often "French name + Arabic name")
    DECLARE @ar INT = PATINDEX(N'%[' + NCHAR(1536) + N'-' + NCHAR(1791) + N']%', @n COLLATE Latin1_General_BIN);
    IF @ar > 0 SET @n = LEFT(@n, @ar - 1);
    -- accents removed (é -> e, â -> a): converting through the Greek code page drops the Latin diacritics
    SET @n = CAST(CAST(@n COLLATE SQL_Latin1_General_CP1253_CI_AI AS VARCHAR(200)) AS NVARCHAR(200));
    -- any non-Latin character left (e.g. Arabic presentation forms) became '?': cut there too
    IF CHARINDEX(N'?', @n) > 0 SET @n = LEFT(@n, CHARINDEX(N'?', @n) - 1);
    -- 2. administrative words, French and English
    SET @n = N' ' + LOWER(@n) + N' ';
    SET @n = REPLACE(@n, N' prefecture d''arrondissements ', N' ');
    SET @n = REPLACE(@n, N' province de ', N' ');
    SET @n = REPLACE(@n, N' province d''', N' ');
    SET @n = REPLACE(@n, N' prefecture de ', N' ');
    SET @n = REPLACE(@n, N' prefecture d''', N' ');
    SET @n = REPLACE(@n, N' prefecture de ', N' ');
    SET @n = REPLACE(@n, N' prefecture of ', N' ');
    SET @n = REPLACE(@n, N' province ', N' ');
    SET @n = REPLACE(@n, N' prefecture ', N' ');
    SET @n = REPLACE(@n, N' prefecture ', N' ');
    -- 3. punctuation to spaces, single spaces
    SET @n = REPLACE(REPLACE(REPLACE(@n, N'-', N' '), N'''', N' '), N'.', N' ');
    WHILE CHARINDEX(N'  ', @n) > 0 SET @n = REPLACE(@n, N'  ', N' ');
    RETURN LTRIM(RTRIM(@n));
END;
GO

CREATE OR ALTER VIEW stg.vHcpProvinceNames AS
SELECT hcp_code, province_name, CAST(stg.fn_CleanProvinceName(province_name) AS NVARCHAR(200)) AS name_clean
FROM stg.HcpPopulation;
GO

IF OBJECT_ID('stg.GeoProvinceNames') IS NULL
CREATE TABLE stg.GeoProvinceNames (
    shape_id    VARCHAR(40)   NOT NULL PRIMARY KEY,
    shape_name  NVARCHAR(200) NOT NULL,
    name_clean  NVARCHAR(200) NOT NULL
);
GO
CREATE OR ALTER PROCEDURE stg.usp_PrepareGeoNames
AS
BEGIN
    SET NOCOUNT ON;
    TRUNCATE TABLE stg.GeoProvinceNames;
    INSERT INTO stg.GeoProvinceNames (shape_id, shape_name, name_clean)
    SELECT shape_id, shape_name, stg.fn_CleanProvinceName(shape_name) FROM stg.Boundaries;
    SELECT COUNT(*) AS GeoNames FROM stg.GeoProvinceNames;
END;
GO

IF OBJECT_ID('stg.ProvinceMatchFuzzy') IS NULL
CREATE TABLE stg.ProvinceMatchFuzzy (
    hcp_code       INT           NOT NULL,
    province_name  NVARCHAR(200) NOT NULL,
    name_clean     NVARCHAR(200) NOT NULL,
    shape_id       VARCHAR(40)   NULL,        -- NULL when the Fuzzy Lookup found no match above the threshold
    geo_name_clean NVARCHAR(200) NULL,
    similarity     REAL          NULL,        -- Fuzzy Lookup _Similarity (0..1)
    confidence     REAL          NULL         -- Fuzzy Lookup _Confidence (0..1)
);
GO

USE DWH_DB;
GO
IF OBJECT_ID('etl.DataFlowAudit') IS NULL
CREATE TABLE etl.DataFlowAudit (
    AuditID      INT IDENTITY(1,1) PRIMARY KEY,
    LoggedAt     DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    PackageName  NVARCHAR(50) NOT NULL,
    RowsRead     INT NOT NULL,
    RowsRejected INT NOT NULL,
    RowsLoaded   INT NOT NULL
);
GO
CREATE OR ALTER PROCEDURE etl.usp_LogDataFlow
    @PackageName NVARCHAR(50), @RowsRead INT, @RowsRejected INT, @RowsLoaded INT
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO etl.DataFlowAudit (PackageName, RowsRead, RowsRejected, RowsLoaded)
    VALUES (@PackageName, @RowsRead, @RowsRejected, @RowsLoaded);
END;
GO

-- Fuzzy Lookup vs the reviewed mapping (dbo.MapProvince, checked by hand)
CREATE OR ALTER VIEW etl.vProvinceFuzzyCheck AS
SELECT f.hcp_code, f.province_name, f.name_clean, f.geo_name_clean, f.similarity, f.confidence,
       f.shape_id AS fuzzy_shape_id, m.ShapeID AS reviewed_shape_id,
       CASE WHEN f.shape_id = m.ShapeID THEN 1 ELSE 0 END AS same_as_reviewed
FROM Staging_DB.stg.ProvinceMatchFuzzy f
LEFT JOIN dbo.MapProvince m ON m.HcpCode = f.hcp_code;
GO

-- Kaggle tables, read by the SSIS export package (one Flat File Destination per view)
-- Text columns are VARCHAR in a UTF-8 collation so the Flat File Destination writes UTF-8 without conversions.
IF SCHEMA_ID('export') IS NULL EXEC('CREATE SCHEMA export');
GO
CREATE OR ALTER VIEW export.provinces AS
SELECT CAST(ProvinceShort COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(200)) AS province, CAST(RegionName COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(200)) AS region, HcpCode AS hcp_code, AreaKm2 AS area_km2,
       PointLat AS lat, PointLon AS lon, Pop2024 AS population_2024, PopUrban2024 AS urban_2024, PopRural2024 AS rural_2024
FROM dbo.DimGeography WHERE GeoLevel = 'Province';
GO
CREATE OR ALTER VIEW export.rainfall_monthly AS
SELECT CAST(CONVERT(CHAR(7), CONVERT(DATE, CONVERT(CHAR(8), f.DateKey)), 120) COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(7)) AS [month], CAST(g.ProvinceShort COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(200)) AS province,
       CAST(g.RegionName COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(200)) AS region, CAST(f.RainMm AS DECIMAL(9,2)) AS rain_mm, CAST(f.NormalMm AS DECIMAL(9,2)) AS normal_1991_2020_mm,
       CAST(100.0 * f.RainMm / NULLIF(f.NormalMm, 0) AS DECIMAL(9,1)) AS pct_of_normal
FROM dbo.FactRainfallMonthly f JOIN dbo.DimGeography g ON g.GeographyKey = f.GeographyKey AND g.GeoLevel = 'Province';
GO
CREATE OR ALTER VIEW export.drought_spi_monthly AS
SELECT CAST(CONVERT(CHAR(7), CONVERT(DATE, CONVERT(CHAR(8), f.DateKey)), 120) COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(7)) AS [month], CAST(g.ProvinceShort COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(200)) AS province,
       CAST(g.RegionName COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(200)) AS region, f.SpiScale AS spi_scale_months, CAST(f.SpiValue AS DECIMAL(6,3)) AS spi, CAST(c.CategoryEn COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(200)) AS category
FROM dbo.FactDroughtIndex f JOIN dbo.DimGeography g ON g.GeographyKey = f.GeographyKey AND g.GeoLevel = 'Province'
JOIN dbo.DimDroughtCategory c ON c.DroughtCategoryKey = f.DroughtCategoryKey;
GO
CREATE OR ALTER VIEW export.vegetation_ndvi_monthly AS
SELECT CAST(CONVERT(CHAR(7), CONVERT(DATE, CONVERT(CHAR(8), f.DateKey)), 120) COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(7)) AS [month], CAST(g.ProvinceShort COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(200)) AS province,
       CAST(g.RegionName COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(200)) AS region, CAST(f.NdviCrop AS DECIMAL(6,4)) AS ndvi_cropland, CAST(f.NdviAll AS DECIMAL(6,4)) AS ndvi_all_land,
       f.CropSharePct AS cropland_share_pct, CAST(f.NdviCropAnomaly AS DECIMAL(6,4)) AS ndvi_cropland_anomaly
FROM dbo.FactVegetationMonthly f JOIN dbo.DimGeography g ON g.GeographyKey = f.GeographyKey AND g.GeoLevel = 'Province';
GO
CREATE OR ALTER VIEW export.weather_daily AS
SELECT CAST(CONVERT(CHAR(10), CONVERT(DATE, CONVERT(CHAR(8), f.DateKey)), 23) COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(10)) AS [date], CAST(g.ProvinceShort COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(200)) AS province,
       CAST(g.RegionName COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(200)) AS region, f.TmaxC AS tmax_c, f.TminC AS tmin_c, f.PrecipMm AS precip_mm, f.Et0Mm AS et0_mm
FROM dbo.FactWeatherDaily f JOIN dbo.DimGeography g ON g.GeographyKey = f.GeographyKey AND g.GeoLevel = 'Province';
GO
CREATE OR ALTER VIEW export.reservoirs AS
SELECT CAST(d.DamName COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(200)) AS dam, CAST(g.ProvinceShort COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(200)) AS province, d.Lat AS lat, d.Lon AS lon,
       d.OsmAreaKm2 AS osm_outline_km2, d.MaxWaterKm2 AS max_water_km2
FROM dbo.DimDam d LEFT JOIN dbo.DimGeography g ON g.GeographyKey = d.GeographyKey;
GO
CREATE OR ALTER VIEW export.dam_water_monthly AS
SELECT CAST(CONVERT(CHAR(7), CONVERT(DATE, CONVERT(CHAR(8), f.DateKey)), 120) COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(7)) AS [month], CAST(d.DamName COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(200)) AS dam,
       CAST(f.WaterKm2 AS DECIMAL(9,3)) AS water_km2, CAST(f.FillIndexPct AS DECIMAL(6,1)) AS pct_of_max_surface,
       CAST(f.ClearPct AS DECIMAL(5,1)) AS visible_pct, CAST(f.IsReliable AS INT) AS reliable, CAST(f.Source COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(200)) AS source
FROM dbo.FactReservoirMonthly f JOIN dbo.DimDam d ON d.DamKey = f.DamKey;
GO
CREATE OR ALTER VIEW export.crops_yearly AS
SELECT f.[Year] AS [year], CAST(c.CropNameEn COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(200)) AS crop, CAST(c.CropGroup COLLATE Latin1_General_100_CI_AS_SC_UTF8 AS VARCHAR(200)) AS crop_group, CAST(c.IsAggregate AS INT) AS is_aggregate,
       f.AreaHa AS area_ha, f.YieldKgHa AS yield_kg_ha, f.ProductionT AS production_t
FROM dbo.FactCropProduction f JOIN dbo.DimCrop c ON c.CropKey = f.CropKey;
GO

SELECT 'stg.RejectedRows' AS obj, OBJECT_ID('Staging_DB.stg.RejectedRows') AS id
UNION ALL SELECT 'etl.DataFlowAudit', OBJECT_ID('DWH_DB.etl.DataFlowAudit')
UNION ALL SELECT 'export views', (SELECT COUNT(*) FROM DWH_DB.sys.views v JOIN DWH_DB.sys.schemas s ON s.schema_id = v.schema_id WHERE s.name = 'export');
