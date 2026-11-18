-- =============================================================
-- Morocco Drought & Water Security Observatory
-- Phase 1 - Script 03: staging tables (the "waiting room")
-- Run in SSMS. Safe to run more than once.
-- Staging tables have the same columns as the CSV files they receive,
-- with no transformation: they are emptied and refilled at each load.
-- =============================================================
USE Staging_DB;
GO
IF SCHEMA_ID('stg') IS NULL
    EXEC('CREATE SCHEMA stg');
GO

-- Step 3: province outlines (from clean/boundaries_provinces.csv)
IF OBJECT_ID('stg.Boundaries') IS NULL
CREATE TABLE stg.Boundaries (
    shape_id    VARCHAR(40)    NOT NULL,   -- geoBoundaries ID of the province
    shape_name  NVARCHAR(200)  NOT NULL,   -- name as written in geoBoundaries (mixed FR/EN/AR)
    area_km2    DECIMAL(12,1)  NOT NULL,
    point_lat   DECIMAL(9,5)   NOT NULL,   -- a point inside the province
    point_lon   DECIMAL(9,5)   NOT NULL
);
GO

-- Step 4: HCP census 2024 legal population (from clean/hcp_population_2024.csv)
-- (re-created if an older version without the code columns exists)
IF OBJECT_ID('stg.HcpPopulation') IS NOT NULL AND COL_LENGTH('stg.HcpPopulation', 'hcp_code') IS NULL
    DROP TABLE stg.HcpPopulation;
IF OBJECT_ID('stg.HcpPopulation') IS NULL
CREATE TABLE stg.HcpPopulation (
    hcp_code       INT           NOT NULL,   -- HCP geographic code of the province
    region_code    INT           NOT NULL,   -- 1..12
    region_name    NVARCHAR(200) NOT NULL,
    province_name  NVARCHAR(200) NOT NULL,   -- official HCP name
    pop_2024       INT           NOT NULL,
    pop_urban_2024 INT           NOT NULL,
    pop_rural_2024 INT           NOT NULL
);
GO
