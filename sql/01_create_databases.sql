-- =============================================================
-- Morocco Drought & Water Security Observatory
-- Step 2 - Script 01: Create the two databases
-- Run in SSMS (connected to localhost). Safe to run more than once.
-- =============================================================
-- Staging_DB = "waiting room": raw data as received, temporary.
-- DWH_DB     = data warehouse: clean, permanent, star schema.
-- =============================================================

IF DB_ID('Staging_DB') IS NULL
    CREATE DATABASE Staging_DB;
GO
IF DB_ID('DWH_DB') IS NULL
    CREATE DATABASE DWH_DB;
GO

-- SIMPLE recovery: SQL Server doesn't keep a full history of every change.
-- Keeps the log file small when loading millions of rows.
-- Fine here because all data can be reloaded from the sources.
ALTER DATABASE Staging_DB SET RECOVERY SIMPLE;
ALTER DATABASE DWH_DB     SET RECOVERY SIMPLE;
GO
