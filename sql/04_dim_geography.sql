-- =============================================================
-- Morocco Drought & Water Security Observatory
-- Phase 1 - Script 04: DimGeography (the "where" dimension)
-- Run in SSMS after 03_staging_tables.sql. Safe to run more than once.
-- =============================================================
USE DWH_DB;
GO

-- -------------------------------------------------------------
-- 1. Mapping table: HCP province code <-> geoBoundaries shape ID
--    Filled by sql/05_map_province.sql (reviewed name matches)
-- -------------------------------------------------------------
IF OBJECT_ID('dbo.MapProvince') IS NULL
CREATE TABLE dbo.MapProvince (
    HcpCode     INT          NOT NULL PRIMARY KEY,
    ShapeID     VARCHAR(40)  NOT NULL UNIQUE,
    HcpName     NVARCHAR(200) NOT NULL,
    GeoName     NVARCHAR(200) NOT NULL,
    MatchScore  DECIMAL(4,3) NOT NULL,     -- name similarity 0..1
    ReviewedOn  DATE         NOT NULL
);
GO

-- -------------------------------------------------------------
-- 2. The dimension: one row per province + one row for the whole country
--    GeographyKey 0 = "Maroc" (national data such as FAOSTAT)
-- -------------------------------------------------------------
IF OBJECT_ID('dbo.DimGeography') IS NULL
CREATE TABLE dbo.DimGeography (
    GeographyKey    INT IDENTITY(1,1) PRIMARY KEY,
    GeoLevel        VARCHAR(10)   NOT NULL,          -- 'Country' or 'Province'
    HcpCode         INT           NULL UNIQUE,       -- HCP code (NULL for the country row)
    ProvinceName    NVARCHAR(200) NOT NULL,          -- official HCP name, e.g. "Province de Settat"
    ProvinceShort   NVARCHAR(150) NOT NULL,          -- short name for charts, e.g. "Settat"
    ProvinceType    NVARCHAR(20)  NOT NULL,          -- 'Province', 'Préfecture' or 'Pays'
    RegionCode      INT           NOT NULL,          -- 1..12 (0 for the country row)
    RegionName      NVARCHAR(200) NOT NULL,
    ShapeID         VARCHAR(40)   NULL,              -- link to the map outline
    AreaKm2         DECIMAL(12,1) NULL,
    PointLat        DECIMAL(9,5)  NULL,              -- point inside the province (weather requests)
    PointLon        DECIMAL(9,5)  NULL,
    Pop2024         INT           NOT NULL,
    PopUrban2024    INT           NOT NULL,
    PopRural2024    INT           NOT NULL,
    RuralSharePct   AS CAST(100.0 * PopRural2024 / NULLIF(Pop2024, 0) AS DECIMAL(5,1)),
    UpdatedAt       DATETIME2(0)  NOT NULL DEFAULT SYSDATETIME()
);
GO

-- -------------------------------------------------------------
-- 3. Load procedure: staging -> DimGeography
--    Fails (and SSIS logs "Failed") if a province has no reviewed mapping.
--    Returns the number of province rows.
-- -------------------------------------------------------------
CREATE OR ALTER PROCEDURE dbo.usp_LoadDimGeography
AS
BEGIN
    SET NOCOUNT ON;

    -- Every HCP province must have a reviewed mapping and an outline
    IF EXISTS (SELECT 1
               FROM Staging_DB.stg.HcpPopulation h
               LEFT JOIN dbo.MapProvince m ON m.HcpCode = h.hcp_code
               LEFT JOIN Staging_DB.stg.Boundaries b ON b.shape_id = m.ShapeID
               WHERE m.HcpCode IS NULL OR b.shape_id IS NULL)
        THROW 50001, 'DimGeography: some HCP provinces have no mapping or no outline. Run scripts\03_match_provinces.py and update sql\05_map_province.sql.', 1;

    DECLARE @act TABLE (a NVARCHAR(10));    -- receives INSERT / UPDATE for the load audit
    ;WITH src AS (
        SELECT h.hcp_code, h.region_code, h.region_name, h.province_name,
               ProvinceShort = LTRIM(
                   CASE
                     WHEN h.province_name LIKE N'Province d''%'    THEN SUBSTRING(h.province_name, 12, 200)
                     WHEN h.province_name LIKE N'Province de %'    THEN SUBSTRING(h.province_name, 13, 200)
                     WHEN h.province_name LIKE N'Préfecture d''%'  THEN SUBSTRING(h.province_name, 14, 200)
                     WHEN h.province_name LIKE N'Préfecture de %'  THEN SUBSTRING(h.province_name, 15, 200)
                     ELSE h.province_name END),
               ProvinceType = CASE WHEN h.province_name LIKE N'Préfecture%' THEN N'Préfecture' ELSE N'Province' END,
               b.shape_id, b.area_km2, b.point_lat, b.point_lon,
               h.pop_2024, h.pop_urban_2024, h.pop_rural_2024
        FROM Staging_DB.stg.HcpPopulation h
        JOIN dbo.MapProvince m        ON m.HcpCode = h.hcp_code
        JOIN Staging_DB.stg.Boundaries b ON b.shape_id = m.ShapeID
    )
    MERGE dbo.DimGeography AS t
    USING src AS s ON t.HcpCode = s.hcp_code
    -- update only when something changed (EXCEPT also compares NULLs correctly)
    WHEN MATCHED AND EXISTS (
        SELECT s.province_name, s.ProvinceShort, s.ProvinceType, s.region_code, s.region_name, s.shape_id,
               s.area_km2, s.point_lat, s.point_lon, s.pop_2024, s.pop_urban_2024, s.pop_rural_2024
        EXCEPT
        SELECT t.ProvinceName, t.ProvinceShort, t.ProvinceType, t.RegionCode, t.RegionName, t.ShapeID,
               t.AreaKm2, t.PointLat, t.PointLon, t.Pop2024, t.PopUrban2024, t.PopRural2024)
    THEN UPDATE SET
        ProvinceName = s.province_name, ProvinceShort = s.ProvinceShort, ProvinceType = s.ProvinceType,
        RegionCode = s.region_code, RegionName = s.region_name,
        ShapeID = s.shape_id, AreaKm2 = s.area_km2, PointLat = s.point_lat, PointLon = s.point_lon,
        Pop2024 = s.pop_2024, PopUrban2024 = s.pop_urban_2024, PopRural2024 = s.pop_rural_2024,
        UpdatedAt = SYSDATETIME()
    WHEN NOT MATCHED THEN INSERT
        (GeoLevel, HcpCode, ProvinceName, ProvinceShort, ProvinceType, RegionCode, RegionName,
         ShapeID, AreaKm2, PointLat, PointLon, Pop2024, PopUrban2024, PopRural2024)
        VALUES ('Province', s.hcp_code, s.province_name, s.ProvinceShort, s.ProvinceType,
                s.region_code, s.region_name, s.shape_id, s.area_km2, s.point_lat, s.point_lon,
                s.pop_2024, s.pop_urban_2024, s.pop_rural_2024)
    OUTPUT $action INTO @act;

    DECLARE @src INT = (SELECT COUNT(*) FROM Staging_DB.stg.HcpPopulation),
            @ins INT = (SELECT COUNT(*) FROM @act WHERE a = 'INSERT'),
            @upd INT = (SELECT COUNT(*) FROM @act WHERE a = 'UPDATE');
    EXEC etl.usp_LogLoad N'dbo.DimGeography', @src, @ins, @upd;

    -- Country row (key 0) = sum of the provinces
    IF NOT EXISTS (SELECT 1 FROM dbo.DimGeography WHERE GeographyKey = 0)
    BEGIN
        SET IDENTITY_INSERT dbo.DimGeography ON;
        INSERT INTO dbo.DimGeography (GeographyKey, GeoLevel, HcpCode, ProvinceName, ProvinceShort,
            ProvinceType, RegionCode, RegionName, Pop2024, PopUrban2024, PopRural2024)
        VALUES (0, 'Country', NULL, N'Maroc', N'Maroc', N'Pays', 0, N'Maroc', 0, 0, 0);
        SET IDENTITY_INSERT dbo.DimGeography OFF;
    END;
    UPDATE g SET Pop2024 = p.Pop, PopUrban2024 = p.Urb, PopRural2024 = p.Rur,
                 AreaKm2 = p.Area, UpdatedAt = SYSDATETIME()
    FROM dbo.DimGeography g
    CROSS JOIN (SELECT SUM(Pop2024) Pop, SUM(PopUrban2024) Urb, SUM(PopRural2024) Rur, SUM(AreaKm2) Area
                FROM dbo.DimGeography WHERE GeoLevel = 'Province') p
    WHERE g.GeographyKey = 0
      AND EXISTS (SELECT p.Pop, p.Urb, p.Rur, p.Area EXCEPT SELECT g.Pop2024, g.PopUrban2024, g.PopRural2024, g.AreaKm2);

    SELECT COUNT(*) AS RowsLoaded FROM dbo.DimGeography WHERE GeoLevel = 'Province';
END;
GO
