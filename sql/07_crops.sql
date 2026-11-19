-- =============================================================
-- Morocco Drought & Water Security Observatory
-- Phase 2 - Script 07: crops (FAOSTAT) -> DimCrop + FactCropProduction
-- Run in SSMS. Safe to run more than once.
-- =============================================================

-- ---------- Staging ----------
USE Staging_DB;
GO
IF OBJECT_ID('stg.FaoCrops') IS NULL
CREATE TABLE stg.FaoCrops (
    [year]        SMALLINT      NOT NULL,
    item_code     INT           NOT NULL,   -- FAOSTAT item code (15 = Wheat)
    item_name     NVARCHAR(200) NOT NULL,
    area_ha       DECIMAL(14,2) NULL,
    yield_kg_ha   DECIMAL(12,2) NULL,
    production_t  DECIMAL(16,2) NULL
);
GO

-- ---------- Warehouse ----------
USE DWH_DB;
GO

-- The "what crop" dimension
IF OBJECT_ID('dbo.DimCrop') IS NULL
CREATE TABLE dbo.DimCrop (
    CropKey      INT IDENTITY(1,1) PRIMARY KEY,
    FaoItemCode  INT           NOT NULL UNIQUE,
    CropNameEn   NVARCHAR(200) NOT NULL,
    CropNameFr   NVARCHAR(200) NOT NULL,          -- French name for key crops, else English
    CropGroup    NVARCHAR(50)  NOT NULL,          -- Céréales, Arboriculture, Agrumes, ...
    IsAggregate  BIT           NOT NULL,          -- FAOSTAT totals such as "Cereals, primary"
    IsKeyCrop    BIT           NOT NULL           -- shown by default in dashboards
);
GO

-- Yearly crop production. Grain: one row per year x geography x crop.
-- Yearly facts point to 1 January of the harvest year in DimDate
-- (so harvest 2024 falls in agricultural season 2023-24).
IF OBJECT_ID('dbo.FactCropProduction') IS NULL
CREATE TABLE dbo.FactCropProduction (
    DateKey       INT           NOT NULL REFERENCES dbo.DimDate(DateKey),
    GeographyKey  INT           NOT NULL REFERENCES dbo.DimGeography(GeographyKey),
    CropKey       INT           NOT NULL REFERENCES dbo.DimCrop(CropKey),
    [Year]        SMALLINT      NOT NULL,
    AreaHa        DECIMAL(14,2) NULL,
    YieldKgHa     DECIMAL(12,2) NULL,
    ProductionT   DECIMAL(16,2) NULL,
    Source        VARCHAR(20)   NOT NULL DEFAULT 'FAOSTAT',
    CONSTRAINT PK_FactCropProduction PRIMARY KEY (DateKey, GeographyKey, CropKey)
);
GO

-- Load procedure: staging -> DimCrop (new crops) -> FactCropProduction (national, key 0)
CREATE OR ALTER PROCEDURE dbo.usp_LoadCrops
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO dbo.DimCrop (FaoItemCode, CropNameEn, CropNameFr, CropGroup, IsAggregate, IsKeyCrop)
    SELECT DISTINCT s.item_code, s.item_name,
        CropNameFr = CASE s.item_code
            WHEN 15 THEN N'Blé' WHEN 44 THEN N'Orge' WHEN 56 THEN N'Maïs' WHEN 75 THEN N'Avoine'
            WHEN 27 THEN N'Riz' WHEN 260 THEN N'Olives' WHEN 490 THEN N'Oranges'
            WHEN 495 THEN N'Mandarines, clémentines' WHEN 497 THEN N'Citrons et limes'
            WHEN 388 THEN N'Tomates' WHEN 116 THEN N'Pommes de terre' WHEN 403 THEN N'Oignons'
            WHEN 577 THEN N'Dattes' WHEN 221 THEN N'Amandes' WHEN 569 THEN N'Figues'
            WHEN 560 THEN N'Raisins' WHEN 157 THEN N'Betterave sucrière' WHEN 156 THEN N'Canne à sucre'
            WHEN 1717 THEN N'Céréales (total)' WHEN 1726 THEN N'Légumineuses (total)'
            WHEN 1804 THEN N'Agrumes (total)'
            ELSE s.item_name END,
        CropGroup = CASE
            WHEN s.item_code IN (15, 44, 56, 75, 27, 71, 79, 83, 108, 1717) THEN N'Céréales'
            WHEN s.item_code IN (490, 495, 497, 507, 512, 1804) THEN N'Agrumes'
            WHEN s.item_code IN (260, 221, 577, 569, 560, 217, 222, 223, 234, 515, 521, 526, 534, 536, 544, 547) THEN N'Arboriculture'
            WHEN s.item_code IN (176, 181, 187, 191, 195, 201, 203, 205, 210, 211, 1726) THEN N'Légumineuses'
            WHEN s.item_code IN (156, 157) THEN N'Cultures sucrières'
            ELSE N'Autres' END,
        IsAggregate = CASE WHEN s.item_code >= 1700 THEN 1 ELSE 0 END,
        IsKeyCrop   = CASE WHEN s.item_code IN (15, 44, 56, 260, 490, 495, 388, 116, 577, 221) THEN 1 ELSE 0 END
    FROM Staging_DB.stg.FaoCrops s
    WHERE NOT EXISTS (SELECT 1 FROM dbo.DimCrop c WHERE c.FaoItemCode = s.item_code);

    DECLARE @act TABLE (a NVARCHAR(10));
    MERGE dbo.FactCropProduction AS t
    USING (
        SELECT DateKey = s.[year] * 10000 + 101, GeographyKey = 0, c.CropKey, s.[year],
               s.area_ha, s.yield_kg_ha, s.production_t
        FROM Staging_DB.stg.FaoCrops s
        JOIN dbo.DimCrop c ON c.FaoItemCode = s.item_code
    ) AS s
    ON t.DateKey = s.DateKey AND t.GeographyKey = s.GeographyKey AND t.CropKey = s.CropKey
    WHEN MATCHED AND EXISTS (SELECT s.area_ha, s.yield_kg_ha, s.production_t
                             EXCEPT SELECT t.AreaHa, t.YieldKgHa, t.ProductionT)
        THEN UPDATE SET AreaHa = s.area_ha, YieldKgHa = s.yield_kg_ha, ProductionT = s.production_t
    WHEN NOT MATCHED THEN INSERT (DateKey, GeographyKey, CropKey, [Year], AreaHa, YieldKgHa, ProductionT)
        VALUES (s.DateKey, s.GeographyKey, s.CropKey, s.[year], s.area_ha, s.yield_kg_ha, s.production_t)
    OUTPUT $action INTO @act;

    DECLARE @src INT = (SELECT COUNT(*) FROM Staging_DB.stg.FaoCrops),
            @ins INT = (SELECT COUNT(*) FROM @act WHERE a = 'INSERT'),
            @upd INT = (SELECT COUNT(*) FROM @act WHERE a = 'UPDATE');
    EXEC etl.usp_LogLoad N'dbo.FactCropProduction', @src, @ins, @upd;

    SELECT COUNT(*) AS RowsLoaded FROM dbo.FactCropProduction WHERE Source = 'FAOSTAT';
END;
GO
