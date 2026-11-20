-- =============================================================
-- Morocco Drought & Water Security Observatory
-- Phase 2 - Script 09: vegetation (MODIS NDVI) and reservoirs (Sentinel-2 water surface)
-- Run in SSMS. Safe to run more than once.
-- =============================================================

-- ---------- Staging ----------
USE Staging_DB;
GO
IF OBJECT_ID('stg.NdviMonthly') IS NULL
CREATE TABLE stg.NdviMonthly (
    month_start    DATE         NOT NULL,
    shape_id       VARCHAR(40)  NOT NULL,
    ndvi_crop      DECIMAL(6,4) NULL,      -- mean NDVI on farmland (NULL if no farmland)
    ndvi_all       DECIMAL(6,4) NULL,      -- mean NDVI on all land
    crop_share_pct DECIMAL(5,1) NOT NULL   -- share of the province that is farmland
);
IF OBJECT_ID('stg.Reservoirs') IS NULL
CREATE TABLE stg.Reservoirs (
    dam_id        INT           NOT NULL,
    dam_name      NVARCHAR(200) NOT NULL,
    osm_area_km2  DECIMAL(9,2)  NOT NULL,
    lat           DECIMAL(9,5)  NOT NULL,
    lon           DECIMAL(9,5)  NOT NULL,
    shape_id      VARCHAR(40)   NOT NULL
);
-- (re-created if an older version without the source column exists)
IF OBJECT_ID('stg.DamWaterMonthly') IS NOT NULL AND COL_LENGTH('stg.DamWaterMonthly', 'source') IS NULL
    DROP TABLE stg.DamWaterMonthly;
IF OBJECT_ID('stg.DamWaterMonthly') IS NULL
CREATE TABLE stg.DamWaterMonthly (
    month_start   DATE          NOT NULL,
    dam_id        INT           NOT NULL,
    water_km2     DECIMAL(9,3)  NOT NULL,
    clear_pct     DECIMAL(5,1)  NOT NULL,
    source        VARCHAR(10)   NOT NULL    -- 'JRC' (Landsat, 2000-2016) or 'S2' (Sentinel-2, 2017+)
);
-- Same lake and month seen by both satellites (2017-2021), for the consistency test
IF OBJECT_ID('stg.DamWaterOverlap') IS NULL
CREATE TABLE stg.DamWaterOverlap (
    month_start    DATE         NOT NULL,
    dam_id         INT          NOT NULL,
    jrc_water_km2  DECIMAL(9,3) NOT NULL,
    jrc_clear_pct  DECIMAL(5,1) NOT NULL,
    s2_water_km2   DECIMAL(9,3) NOT NULL,
    s2_clear_pct   DECIMAL(5,1) NOT NULL
);
GO

-- ---------- Warehouse ----------
USE DWH_DB;
GO

-- Vegetation per province and month, with the 2001-2020 normal of the same month and the anomaly
IF OBJECT_ID('dbo.FactVegetationMonthly') IS NULL
CREATE TABLE dbo.FactVegetationMonthly (
    DateKey          INT          NOT NULL REFERENCES dbo.DimDate(DateKey),
    GeographyKey     INT          NOT NULL REFERENCES dbo.DimGeography(GeographyKey),
    NdviCrop         DECIMAL(6,4) NULL,
    NdviAll          DECIMAL(6,4) NULL,
    CropSharePct     DECIMAL(5,1) NOT NULL,
    NdviCropNormal   DECIMAL(6,4) NULL,     -- average of the same month, 2001-2020
    NdviCropAnomaly  DECIMAL(6,4) NULL,     -- NdviCrop - normal (negative = less green than usual)
    NdviAllNormal    DECIMAL(6,4) NULL,
    NdviAllAnomaly   DECIMAL(6,4) NULL,
    CONSTRAINT PK_FactVegetationMonthly PRIMARY KEY (DateKey, GeographyKey)
);
GO

-- Reservoirs (from OpenStreetMap). Natural key = name.
IF OBJECT_ID('dbo.DimDam') IS NULL
CREATE TABLE dbo.DimDam (
    DamKey        INT IDENTITY(1,1) PRIMARY KEY,
    DamName       NVARCHAR(200) NOT NULL UNIQUE,
    GeographyKey  INT           NOT NULL REFERENCES dbo.DimGeography(GeographyKey),  -- province of the lake
    OsmAreaKm2    DECIMAL(9,2)  NOT NULL,     -- outline area in OpenStreetMap (~ full lake)
    Lat           DECIMAL(9,5)  NOT NULL,
    Lon           DECIMAL(9,5)  NOT NULL,
    MaxWaterKm2   DECIMAL(9,3)  NULL          -- largest water surface observed (clear months)
);
GO

-- Monthly water surface per reservoir (Sentinel-2). Grain: month x dam.
IF OBJECT_ID('dbo.FactReservoirMonthly') IS NULL
CREATE TABLE dbo.FactReservoirMonthly (
    DateKey       INT          NOT NULL REFERENCES dbo.DimDate(DateKey),
    DamKey        INT          NOT NULL REFERENCES dbo.DimDam(DamKey),
    WaterKm2      DECIMAL(9,3) NOT NULL,
    ClearPct      DECIMAL(5,1) NOT NULL,      -- share of the lake seen without clouds
    IsReliable    BIT          NOT NULL,      -- ClearPct >= 80
    FillIndexPct  DECIMAL(5,1) NULL,          -- WaterKm2 / MaxWaterKm2 x 100 (satellite fill indicator)
    Source        VARCHAR(10)  NOT NULL DEFAULT 'S2',   -- 'JRC' (2000-2016) or 'S2' (2017+)
    CONSTRAINT PK_FactReservoirMonthly PRIMARY KEY (DateKey, DamKey)
);
GO
IF COL_LENGTH('dbo.FactReservoirMonthly', 'Source') IS NULL
    ALTER TABLE dbo.FactReservoirMonthly ADD Source VARCHAR(10) NOT NULL
        CONSTRAINT DF_FactReservoirMonthly_Source DEFAULT 'S2';
GO

-- ---------- Load procedures ----------
CREATE OR ALTER PROCEDURE dbo.usp_LoadVegetation
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @act TABLE (a NVARCHAR(10));
    MERGE dbo.FactVegetationMonthly AS t
    USING (SELECT DateKey = CONVERT(INT, CONVERT(CHAR(8), s.month_start, 112)), g.GeographyKey,
                  s.ndvi_crop, s.ndvi_all, s.crop_share_pct
           FROM Staging_DB.stg.NdviMonthly s JOIN dbo.DimGeography g ON g.ShapeID = s.shape_id) AS s
    ON t.DateKey = s.DateKey AND t.GeographyKey = s.GeographyKey
    WHEN MATCHED AND EXISTS (SELECT s.ndvi_crop, s.ndvi_all, s.crop_share_pct
                             EXCEPT SELECT t.NdviCrop, t.NdviAll, t.CropSharePct)
        THEN UPDATE SET NdviCrop = s.ndvi_crop, NdviAll = s.ndvi_all, CropSharePct = s.crop_share_pct
    WHEN NOT MATCHED THEN INSERT (DateKey, GeographyKey, NdviCrop, NdviAll, CropSharePct)
        VALUES (s.DateKey, s.GeographyKey, s.ndvi_crop, s.ndvi_all, s.crop_share_pct)
    OUTPUT $action INTO @act;

    DECLARE @src INT = (SELECT COUNT(*) FROM Staging_DB.stg.NdviMonthly),
            @ins INT = (SELECT COUNT(*) FROM @act WHERE a = 'INSERT'),
            @upd INT = (SELECT COUNT(*) FROM @act WHERE a = 'UPDATE');
    EXEC etl.usp_LogLoad N'dbo.FactVegetationMonthly', @src, @ins, @upd;

    ;WITH n AS (
        SELECT f.GeographyKey, d.[Month], AVG(f.NdviCrop) AS CropN, AVG(f.NdviAll) AS AllN
        FROM dbo.FactVegetationMonthly f JOIN dbo.DimDate d ON d.DateKey = f.DateKey
        WHERE d.[Year] BETWEEN 2001 AND 2020
        GROUP BY f.GeographyKey, d.[Month])
    UPDATE f SET NdviCropNormal = n.CropN, NdviCropAnomaly = f.NdviCrop - n.CropN,
                 NdviAllNormal  = n.AllN,  NdviAllAnomaly  = f.NdviAll  - n.AllN
    FROM dbo.FactVegetationMonthly f
    JOIN dbo.DimDate d ON d.DateKey = f.DateKey
    JOIN n ON n.GeographyKey = f.GeographyKey AND n.[Month] = d.[Month]
    WHERE EXISTS (SELECT CAST(n.CropN AS DECIMAL(6,4)), CAST(f.NdviCrop - n.CropN AS DECIMAL(6,4)),
                         CAST(n.AllN AS DECIMAL(6,4)),  CAST(f.NdviAll - n.AllN AS DECIMAL(6,4))
                  EXCEPT SELECT f.NdviCropNormal, f.NdviCropAnomaly, f.NdviAllNormal, f.NdviAllAnomaly);

    SELECT COUNT(*) AS RowsLoaded FROM dbo.FactVegetationMonthly;
END;
GO

CREATE OR ALTER PROCEDURE dbo.usp_LoadReservoirs
AS
BEGIN
    SET NOCOUNT ON;
    MERGE dbo.DimDam AS t
    USING (SELECT r.dam_name, g.GeographyKey, r.osm_area_km2, r.lat, r.lon
           FROM Staging_DB.stg.Reservoirs r JOIN dbo.DimGeography g ON g.ShapeID = r.shape_id) AS s
    ON t.DamName = s.dam_name
    WHEN MATCHED AND EXISTS (SELECT s.GeographyKey, s.osm_area_km2, s.lat, s.lon
                             EXCEPT SELECT t.GeographyKey, t.OsmAreaKm2, t.Lat, t.Lon)
        THEN UPDATE SET GeographyKey = s.GeographyKey, OsmAreaKm2 = s.osm_area_km2, Lat = s.lat, Lon = s.lon
    WHEN NOT MATCHED THEN INSERT (DamName, GeographyKey, OsmAreaKm2, Lat, Lon)
        VALUES (s.dam_name, s.GeographyKey, s.osm_area_km2, s.lat, s.lon);

    DECLARE @act TABLE (a NVARCHAR(10));
    MERGE dbo.FactReservoirMonthly AS t
    USING (SELECT DateKey = CONVERT(INT, CONVERT(CHAR(8), w.month_start, 112)), d.DamKey,
                  w.water_km2, w.clear_pct, IsReliable = CASE WHEN w.clear_pct >= 80 THEN 1 ELSE 0 END,
                  w.source
           FROM Staging_DB.stg.DamWaterMonthly w
           JOIN Staging_DB.stg.Reservoirs r ON r.dam_id = w.dam_id
           JOIN dbo.DimDam d ON d.DamName = r.dam_name) AS s
    ON t.DateKey = s.DateKey AND t.DamKey = s.DamKey
    WHEN MATCHED AND EXISTS (SELECT s.water_km2, s.clear_pct, s.IsReliable, s.source
                             EXCEPT SELECT t.WaterKm2, t.ClearPct, t.IsReliable, t.Source)
        THEN UPDATE SET WaterKm2 = s.water_km2, ClearPct = s.clear_pct, IsReliable = s.IsReliable, Source = s.source
    WHEN NOT MATCHED THEN INSERT (DateKey, DamKey, WaterKm2, ClearPct, IsReliable, Source)
        VALUES (s.DateKey, s.DamKey, s.water_km2, s.clear_pct, s.IsReliable, s.source)
    OUTPUT $action INTO @act;

    DECLARE @src INT = (SELECT COUNT(*) FROM Staging_DB.stg.DamWaterMonthly),
            @ins INT = (SELECT COUNT(*) FROM @act WHERE a = 'INSERT'),
            @upd INT = (SELECT COUNT(*) FROM @act WHERE a = 'UPDATE');
    EXEC etl.usp_LogLoad N'dbo.FactReservoirMonthly', @src, @ins, @upd;

    -- Fill indicator: water surface as % of the largest surface seen in a reliable month
    -- (only rows whose value really changes are rewritten)
    UPDATE d SET MaxWaterKm2 = x.MaxW
    FROM dbo.DimDam d
    JOIN (SELECT DamKey, MAX(WaterKm2) AS MaxW FROM dbo.FactReservoirMonthly WHERE IsReliable = 1 GROUP BY DamKey) x
      ON x.DamKey = d.DamKey
    WHERE EXISTS (SELECT x.MaxW EXCEPT SELECT d.MaxWaterKm2);
    UPDATE f SET FillIndexPct = CASE WHEN d.MaxWaterKm2 > 0 THEN 100.0 * f.WaterKm2 / d.MaxWaterKm2 END
    FROM dbo.FactReservoirMonthly f JOIN dbo.DimDam d ON d.DamKey = f.DamKey
    WHERE EXISTS (SELECT CAST(CASE WHEN d.MaxWaterKm2 > 0 THEN 100.0 * f.WaterKm2 / d.MaxWaterKm2 END AS DECIMAL(5,1))
                  EXCEPT SELECT f.FillIndexPct);

    SELECT COUNT(*) AS RowsLoaded FROM dbo.FactReservoirMonthly;
END;
GO
