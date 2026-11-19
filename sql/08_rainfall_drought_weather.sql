-- =============================================================
-- Morocco Drought & Water Security Observatory
-- Phase 2 - Script 08: rainfall (CHIRPS), drought index (SPI), daily weather (Open-Meteo)
-- Run in SSMS. Safe to run more than once.
-- =============================================================

-- ---------- Staging ----------
USE Staging_DB;
GO
IF OBJECT_ID('stg.ChirpsMonthly') IS NULL
CREATE TABLE stg.ChirpsMonthly (
    month_start DATE         NOT NULL,     -- first day of the month
    shape_id    VARCHAR(40)  NOT NULL,     -- province (geoBoundaries ID)
    rain_mm     DECIMAL(9,2) NOT NULL      -- mean monthly rainfall over the province
);
IF OBJECT_ID('stg.SpiMonthly') IS NULL
CREATE TABLE stg.SpiMonthly (
    month_start DATE         NOT NULL,
    shape_id    VARCHAR(40)  NOT NULL,
    spi_scale   TINYINT      NOT NULL,     -- 1, 3, 6 or 12 months
    spi         DECIMAL(6,3) NOT NULL
);
IF OBJECT_ID('stg.WeatherDaily') IS NULL
CREATE TABLE stg.WeatherDaily (
    [day]       DATE         NOT NULL,
    shape_id    VARCHAR(40)  NOT NULL,
    tmax_c      DECIMAL(5,1) NULL,
    tmin_c      DECIMAL(5,1) NULL,
    precip_mm   DECIMAL(7,2) NULL,
    et0_mm      DECIMAL(6,2) NULL          -- reference evapotranspiration (FAO-56)
);
GO

-- ---------- Warehouse ----------
USE DWH_DB;
GO

-- Monthly rainfall per province, with the 1991-2020 normal and the anomaly.
-- DateKey = first day of the month.
IF OBJECT_ID('dbo.FactRainfallMonthly') IS NULL
CREATE TABLE dbo.FactRainfallMonthly (
    DateKey       INT          NOT NULL REFERENCES dbo.DimDate(DateKey),
    GeographyKey  INT          NOT NULL REFERENCES dbo.DimGeography(GeographyKey),
    RainMm        DECIMAL(9,2) NOT NULL,
    NormalMm      DECIMAL(9,2) NULL,       -- average of the same month over 1991-2020
    AnomalyPct    DECIMAL(9,1) NULL,       -- RainMm as % of normal (100 = normal)
    CONSTRAINT PK_FactRainfallMonthly PRIMARY KEY (DateKey, GeographyKey)
);
GO

-- Drought categories (McKee et al. 1993, used by the WMO SPI guide)
IF OBJECT_ID('dbo.DimDroughtCategory') IS NULL
BEGIN
    CREATE TABLE dbo.DimDroughtCategory (
        DroughtCategoryKey TINYINT      NOT NULL PRIMARY KEY,
        CategoryFr         NVARCHAR(40) NOT NULL,
        CategoryEn         NVARCHAR(40) NOT NULL,
        MinSpi             DECIMAL(6,3) NOT NULL,    -- inclusive
        MaxSpi             DECIMAL(6,3) NOT NULL,    -- exclusive
        IsDrought          BIT          NOT NULL,
        ColorHex           CHAR(7)      NOT NULL
    );
    INSERT INTO dbo.DimDroughtCategory VALUES
    (1, N'Extrêmement humide',  N'Extremely wet',    2.000,  99.000, 0, '#1F4E9C'),
    (2, N'Très humide',         N'Very wet',         1.500,   2.000, 0, '#3D7CC9'),
    (3, N'Modérément humide',   N'Moderately wet',   1.000,   1.500, 0, '#8DB8E8'),
    (4, N'Proche de la normale',N'Near normal',     -1.000,   1.000, 0, '#D9D9D9'),
    (5, N'Sécheresse modérée',  N'Moderate drought',-1.500,  -1.000, 1, '#F4C26B'),
    (6, N'Sécheresse sévère',   N'Severe drought',  -2.000,  -1.500, 1, '#E07B39'),
    (7, N'Sécheresse extrême',  N'Extreme drought', -99.000, -2.000, 1, '#B3261E');
END;
GO

-- SPI per province, month and time scale. Grain: month x province x scale.
IF OBJECT_ID('dbo.FactDroughtIndex') IS NULL
CREATE TABLE dbo.FactDroughtIndex (
    DateKey            INT          NOT NULL REFERENCES dbo.DimDate(DateKey),
    GeographyKey       INT          NOT NULL REFERENCES dbo.DimGeography(GeographyKey),
    SpiScale           TINYINT      NOT NULL,     -- 1, 3, 6, 12 months
    SpiValue           DECIMAL(6,3) NOT NULL,
    DroughtCategoryKey TINYINT      NOT NULL REFERENCES dbo.DimDroughtCategory(DroughtCategoryKey),
    CONSTRAINT PK_FactDroughtIndex PRIMARY KEY (DateKey, GeographyKey, SpiScale)
);
GO

-- Daily weather per province (point inside the province). Grain: day x province.
IF OBJECT_ID('dbo.FactWeatherDaily') IS NULL
CREATE TABLE dbo.FactWeatherDaily (
    DateKey       INT          NOT NULL REFERENCES dbo.DimDate(DateKey),
    GeographyKey  INT          NOT NULL REFERENCES dbo.DimGeography(GeographyKey),
    TmaxC         DECIMAL(5,1) NULL,
    TminC         DECIMAL(5,1) NULL,
    PrecipMm      DECIMAL(7,2) NULL,
    Et0Mm         DECIMAL(6,2) NULL,
    CONSTRAINT PK_FactWeatherDaily PRIMARY KEY (DateKey, GeographyKey)
);
GO

-- ---------- Load procedures ----------

CREATE OR ALTER PROCEDURE dbo.usp_LoadRainfall
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM Staging_DB.stg.ChirpsMonthly s
               LEFT JOIN dbo.DimGeography g ON g.ShapeID = s.shape_id WHERE g.GeographyKey IS NULL)
        THROW 50002, 'Rainfall: some shape_id values are not in DimGeography.', 1;

    DECLARE @act TABLE (a NVARCHAR(10));
    MERGE dbo.FactRainfallMonthly AS t
    USING (SELECT DateKey = CONVERT(INT, CONVERT(CHAR(8), s.month_start, 112)), g.GeographyKey, s.rain_mm
           FROM Staging_DB.stg.ChirpsMonthly s
           JOIN dbo.DimGeography g ON g.ShapeID = s.shape_id) AS s
    ON t.DateKey = s.DateKey AND t.GeographyKey = s.GeographyKey
    WHEN MATCHED AND t.RainMm <> s.rain_mm THEN UPDATE SET RainMm = s.rain_mm
    WHEN NOT MATCHED THEN INSERT (DateKey, GeographyKey, RainMm) VALUES (s.DateKey, s.GeographyKey, s.rain_mm)
    OUTPUT $action INTO @act;

    DECLARE @src INT = (SELECT COUNT(*) FROM Staging_DB.stg.ChirpsMonthly),
            @ins INT = (SELECT COUNT(*) FROM @act WHERE a = 'INSERT'),
            @upd INT = (SELECT COUNT(*) FROM @act WHERE a = 'UPDATE');
    EXEC etl.usp_LogLoad N'dbo.FactRainfallMonthly', @src, @ins, @upd;

    -- Normal = average of the same calendar month over 1991-2020 (WMO reference period)
    ;WITH normals AS (
        SELECT f.GeographyKey, d.[Month], AVG(f.RainMm) AS NormalMm
        FROM dbo.FactRainfallMonthly f
        JOIN dbo.DimDate d ON d.DateKey = f.DateKey
        WHERE d.[Year] BETWEEN 1991 AND 2020
        GROUP BY f.GeographyKey, d.[Month]
        HAVING COUNT(*) = 30
    )
    UPDATE f SET NormalMm   = n.NormalMm,
                 AnomalyPct = CASE WHEN n.NormalMm > 0 THEN 100.0 * f.RainMm / n.NormalMm END
    FROM dbo.FactRainfallMonthly f
    JOIN dbo.DimDate d ON d.DateKey = f.DateKey
    JOIN normals n ON n.GeographyKey = f.GeographyKey AND n.[Month] = d.[Month]
    WHERE EXISTS (SELECT CAST(n.NormalMm AS DECIMAL(9,2)),
                         CAST(CASE WHEN n.NormalMm > 0 THEN 100.0 * f.RainMm / n.NormalMm END AS DECIMAL(9,1))
                  EXCEPT SELECT f.NormalMm, f.AnomalyPct);       -- only rows whose normal really changed

    SELECT COUNT(*) AS RowsLoaded FROM dbo.FactRainfallMonthly;
END;
GO

CREATE OR ALTER PROCEDURE dbo.usp_LoadDroughtIndex
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @act TABLE (a NVARCHAR(10));
    MERGE dbo.FactDroughtIndex AS t
    USING (SELECT DateKey = CONVERT(INT, CONVERT(CHAR(8), s.month_start, 112)), g.GeographyKey,
                  s.spi_scale, s.spi, c.DroughtCategoryKey
           FROM Staging_DB.stg.SpiMonthly s
           JOIN dbo.DimGeography g ON g.ShapeID = s.shape_id
           JOIN dbo.DimDroughtCategory c ON s.spi >= c.MinSpi AND s.spi < c.MaxSpi) AS s
    ON t.DateKey = s.DateKey AND t.GeographyKey = s.GeographyKey AND t.SpiScale = s.spi_scale
    WHEN MATCHED AND (t.SpiValue <> s.spi OR t.DroughtCategoryKey <> s.DroughtCategoryKey)
        THEN UPDATE SET SpiValue = s.spi, DroughtCategoryKey = s.DroughtCategoryKey
    WHEN NOT MATCHED THEN INSERT (DateKey, GeographyKey, SpiScale, SpiValue, DroughtCategoryKey)
        VALUES (s.DateKey, s.GeographyKey, s.spi_scale, s.spi, s.DroughtCategoryKey)
    OUTPUT $action INTO @act;

    DECLARE @src INT = (SELECT COUNT(*) FROM Staging_DB.stg.SpiMonthly),
            @ins INT = (SELECT COUNT(*) FROM @act WHERE a = 'INSERT'),
            @upd INT = (SELECT COUNT(*) FROM @act WHERE a = 'UPDATE');
    EXEC etl.usp_LogLoad N'dbo.FactDroughtIndex', @src, @ins, @upd;
    SELECT COUNT(*) AS RowsLoaded FROM dbo.FactDroughtIndex;
END;
GO

CREATE OR ALTER PROCEDURE dbo.usp_LoadWeather
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @act TABLE (a NVARCHAR(10));
    MERGE dbo.FactWeatherDaily AS t
    USING (SELECT DateKey = CONVERT(INT, CONVERT(CHAR(8), s.[day], 112)), g.GeographyKey,
                  s.tmax_c, s.tmin_c, s.precip_mm, s.et0_mm
           FROM Staging_DB.stg.WeatherDaily s
           JOIN dbo.DimGeography g ON g.ShapeID = s.shape_id) AS s
    ON t.DateKey = s.DateKey AND t.GeographyKey = s.GeographyKey
    WHEN MATCHED AND EXISTS (SELECT s.tmax_c, s.tmin_c, s.precip_mm, s.et0_mm
                             EXCEPT SELECT t.TmaxC, t.TminC, t.PrecipMm, t.Et0Mm)
        THEN UPDATE SET TmaxC = s.tmax_c, TminC = s.tmin_c, PrecipMm = s.precip_mm, Et0Mm = s.et0_mm
    WHEN NOT MATCHED THEN INSERT (DateKey, GeographyKey, TmaxC, TminC, PrecipMm, Et0Mm)
        VALUES (s.DateKey, s.GeographyKey, s.tmax_c, s.tmin_c, s.precip_mm, s.et0_mm)
    OUTPUT $action INTO @act;

    DECLARE @src INT = (SELECT COUNT(*) FROM Staging_DB.stg.WeatherDaily),
            @ins INT = (SELECT COUNT(*) FROM @act WHERE a = 'INSERT'),
            @upd INT = (SELECT COUNT(*) FROM @act WHERE a = 'UPDATE');
    EXEC etl.usp_LogLoad N'dbo.FactWeatherDaily', @src, @ins, @upd;
    SELECT COUNT(*) AS RowsLoaded FROM dbo.FactWeatherDaily;
END;
GO
