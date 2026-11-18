-- =============================================================
-- Morocco Drought & Water Security Observatory
-- Phase 1 - Script 06: DimDate (the "when" dimension)
-- One row per day from 1940-01-01 (start of Open-Meteo data) to 2030-12-31.
-- Run in SSMS. Safe to run more than once (only adds missing days).
-- =============================================================
USE DWH_DB;
GO

IF OBJECT_ID('dbo.DimDate') IS NULL
CREATE TABLE dbo.DimDate (
    DateKey          INT           NOT NULL PRIMARY KEY,   -- yyyymmdd, e.g. 20240315
    [Date]           DATE          NOT NULL UNIQUE,
    [Year]           SMALLINT      NOT NULL,
    [Quarter]        TINYINT       NOT NULL,
    [Month]          TINYINT       NOT NULL,
    MonthNameFr      NVARCHAR(12)  NOT NULL,               -- Janvier ...
    MonthNameAr      NVARCHAR(12)  NOT NULL,               -- يناير ... (names used in Morocco)
    YearMonth        CHAR(7)       NOT NULL,               -- '2024-03'
    MonthStart       DATE          NOT NULL,               -- first day of the month (monthly facts join here)
    [Day]            TINYINT       NOT NULL,
    DayOfYear        SMALLINT      NOT NULL,
    IsoWeekday       TINYINT       NOT NULL,               -- 1 = Monday ... 7 = Sunday
    DayNameFr        NVARCHAR(10)  NOT NULL,
    IsWeekend        BIT           NOT NULL,               -- Saturday or Sunday
    -- Agricultural season: September -> August (rain from autumn feeds the next summer harvest)
    AgriSeasonStartYear SMALLINT   NOT NULL,               -- 2023 for Sept 2023 ... Aug 2024
    AgriSeason       CHAR(7)       NOT NULL,               -- '2023-24'
    AgriSeasonMonthNo TINYINT      NOT NULL,               -- September = 1 ... August = 12
    -- Hijri calendar: Umm al-Qura calendar (culture ar-SA). Morocco follows its own moon
    -- sighting, which is often 1 day later (e.g. Ramadan 2024: Umm al-Qura 11 March,
    -- Morocco 12 March). Precise enough for monthly drought analysis.
    HijriYear        SMALLINT      NOT NULL,
    HijriMonth       TINYINT       NOT NULL,
    IsRamadan        BIT           NOT NULL
);
GO

;WITH n AS (            -- numbers 0, 1, 2, ... (enough for 91 years of days)
    SELECT TOP (DATEDIFF(DAY, '1940-01-01', '2030-12-31') + 1)
           ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS i
    FROM sys.all_objects a CROSS JOIN sys.all_objects b
),
d AS (
    SELECT DATEADD(DAY, i, CAST('1940-01-01' AS DATE)) AS dt FROM n
),
h AS (                  -- Hijri date as text 'yyyy/MM/dd' (Umm al-Qura calendar)
    SELECT dt, FORMAT(dt, 'yyyy/MM/dd', 'ar-SA') AS hij
    FROM d
)
INSERT INTO dbo.DimDate
SELECT
    DateKey          = YEAR(dt) * 10000 + MONTH(dt) * 100 + DAY(dt),
    [Date]           = dt,
    [Year]           = YEAR(dt),
    [Quarter]        = DATEPART(QUARTER, dt),
    [Month]          = MONTH(dt),
    MonthNameFr      = CHOOSE(MONTH(dt), N'Janvier', N'Février', N'Mars', N'Avril', N'Mai', N'Juin',
                              N'Juillet', N'Août', N'Septembre', N'Octobre', N'Novembre', N'Décembre'),
    MonthNameAr      = CHOOSE(MONTH(dt), N'يناير', N'فبراير', N'مارس', N'أبريل', N'ماي', N'يونيو',
                              N'يوليوز', N'غشت', N'شتنبر', N'أكتوبر', N'نونبر', N'دجنبر'),
    YearMonth        = CONVERT(CHAR(7), dt, 120),
    MonthStart       = DATEFROMPARTS(YEAR(dt), MONTH(dt), 1),
    [Day]            = DAY(dt),
    DayOfYear        = DATEPART(DAYOFYEAR, dt),
    IsoWeekday       = DATEDIFF(DAY, '1900-01-01', dt) % 7 + 1,       -- 1900-01-01 was a Monday
    DayNameFr        = CHOOSE(DATEDIFF(DAY, '1900-01-01', dt) % 7 + 1,
                              N'Lundi', N'Mardi', N'Mercredi', N'Jeudi', N'Vendredi', N'Samedi', N'Dimanche'),
    IsWeekend        = CASE WHEN DATEDIFF(DAY, '1900-01-01', dt) % 7 + 1 >= 6 THEN 1 ELSE 0 END,
    AgriSeasonStartYear = CASE WHEN MONTH(dt) >= 9 THEN YEAR(dt) ELSE YEAR(dt) - 1 END,
    AgriSeason       = CAST(CASE WHEN MONTH(dt) >= 9 THEN YEAR(dt) ELSE YEAR(dt) - 1 END AS CHAR(4)) + '-'
                       + RIGHT(CAST(CASE WHEN MONTH(dt) >= 9 THEN YEAR(dt) + 1 ELSE YEAR(dt) END AS CHAR(4)), 2),
    AgriSeasonMonthNo = (MONTH(dt) + 3) % 12 + 1,                   -- Sep=1, Oct=2, ..., Aug=12
    HijriYear        = CAST(LEFT(hij, 4) AS SMALLINT),
    HijriMonth       = CAST(SUBSTRING(hij, 6, 2) AS TINYINT),
    IsRamadan        = CASE WHEN SUBSTRING(hij, 6, 2) = '09' THEN 1 ELSE 0 END
FROM h
WHERE NOT EXISTS (SELECT 1 FROM dbo.DimDate x WHERE x.[Date] = h.dt);

-- Refresh the Hijri columns of existing rows (in case they were built with another method)
UPDATE x SET HijriYear  = CAST(LEFT(FORMAT(x.[Date], 'yyyy/MM/dd', 'ar-SA'), 4) AS SMALLINT),
             HijriMonth = CAST(SUBSTRING(FORMAT(x.[Date], 'yyyy/MM/dd', 'ar-SA'), 6, 2) AS TINYINT),
             IsRamadan  = CASE WHEN SUBSTRING(FORMAT(x.[Date], 'yyyy/MM/dd', 'ar-SA'), 6, 2) = '09' THEN 1 ELSE 0 END
FROM dbo.DimDate x;

SELECT COUNT(*) AS DaysInDimDate FROM dbo.DimDate;   -- expected 33,238 (91 years x 365 + 23 leap days)
GO
