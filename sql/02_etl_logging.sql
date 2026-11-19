-- =============================================================
-- Morocco Drought & Water Security Observatory
-- Step 2 - Script 02: ETL logging (schema, log table, procedures)
-- Run in SSMS after 01_create_databases.sql. Safe to run more than once.
-- =============================================================

USE DWH_DB;
GO

-- -------------------------------------------------------------
-- 1. Schema "etl": a folder for technical tables (kept apart from
--    business tables like facts and dimensions)
-- -------------------------------------------------------------
IF SCHEMA_ID('etl') IS NULL
    EXEC('CREATE SCHEMA etl');
GO

-- -------------------------------------------------------------
-- 2. Logbook table: every SSIS run writes one line here
-- -------------------------------------------------------------
IF OBJECT_ID('etl.RunLog') IS NULL
CREATE TABLE etl.RunLog (
    RunID        INT IDENTITY(1,1) PRIMARY KEY,                -- automatic number: 1, 2, 3...
    PackageName  NVARCHAR(200)  NOT NULL,                       -- which SSIS package ran
    StartTime    DATETIME2(0)   NOT NULL DEFAULT SYSDATETIME(), -- filled automatically
    EndTime      DATETIME2(0)   NULL,                           -- filled at the end
    RowsLoaded   INT            NULL,                           -- how many rows were loaded
    Status       VARCHAR(20)    NOT NULL DEFAULT 'Running'
                 CHECK (Status IN ('Running','Success','Failed')),
    ErrorMessage NVARCHAR(4000) NULL,                           -- error text if it failed
    MachineName  NVARCHAR(128)  NOT NULL DEFAULT HOST_NAME()    -- which PC ran it
);
GO

-- -------------------------------------------------------------
-- 3. Called at the START of each SSIS package:
--    creates a "Running" line and returns its RunID
-- -------------------------------------------------------------
CREATE OR ALTER PROCEDURE etl.usp_StartRun
    @PackageName NVARCHAR(200),
    @RunID       INT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO etl.RunLog (PackageName) VALUES (@PackageName);
    SET @RunID = SCOPE_IDENTITY();   -- the number SQL Server just gave to the new line
END;
GO

-- -------------------------------------------------------------
-- 3b. Load audit (Phase 3): every load procedure records how many rows it inserted, updated
--     or left unchanged. Proves that re-running a load changes nothing and that a new month
--     only adds that month.
-- -------------------------------------------------------------
IF OBJECT_ID('etl.LoadAudit') IS NULL
CREATE TABLE etl.LoadAudit (
    AuditID       INT IDENTITY(1,1) PRIMARY KEY,
    TableName     NVARCHAR(128) NOT NULL,
    LoadedAt      DATETIME2(0)  NOT NULL DEFAULT SYSDATETIME(),
    SourceRows    INT           NOT NULL,     -- rows offered by staging
    RowsInserted  INT           NOT NULL,
    RowsUpdated   INT           NOT NULL,
    RowsUnchanged AS (SourceRows - RowsInserted - RowsUpdated)
);
GO
CREATE OR ALTER PROCEDURE etl.usp_LogLoad
    @TableName NVARCHAR(128), @SourceRows INT, @RowsInserted INT, @RowsUpdated INT
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO etl.LoadAudit (TableName, SourceRows, RowsInserted, RowsUpdated)
    VALUES (@TableName, @SourceRows, @RowsInserted, @RowsUpdated);
END;
GO

-- -------------------------------------------------------------
-- 4. Called at the END of each SSIS package:
--    marks the line as Success or Failed
-- -------------------------------------------------------------
CREATE OR ALTER PROCEDURE etl.usp_EndRun
    @RunID        INT,
    @Status       VARCHAR(20),
    @RowsLoaded   INT            = NULL,
    @ErrorMessage NVARCHAR(4000) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE etl.RunLog
    SET EndTime      = SYSDATETIME(),
        Status       = @Status,
        RowsLoaded   = @RowsLoaded,
        ErrorMessage = @ErrorMessage
    WHERE RunID = @RunID;
END;
GO
