-- =============================================================
-- Test for Step 2 - Script 02 (ETL logging)
-- Expected: 2 rows -> Test_Success (Success, 100 rows)
--                     Test_Failure (Failed, 0 rows, "This is a test error")
-- =============================================================
USE DWH_DB;
GO

-- Test 1: a run that succeeds
DECLARE @id INT;
EXEC etl.usp_StartRun @PackageName = N'Test_Success', @RunID = @id OUTPUT;
EXEC etl.usp_EndRun   @RunID = @id, @Status = 'Success', @RowsLoaded = 100;

-- Test 2: a run that fails
EXEC etl.usp_StartRun @PackageName = N'Test_Failure', @RunID = @id OUTPUT;
EXEC etl.usp_EndRun   @RunID = @id, @Status = 'Failed', @RowsLoaded = 0,
                      @ErrorMessage = N'This is a test error';

SELECT * FROM etl.RunLog ORDER BY RunID;
GO

-- Bonus test: this MUST fail with a CHECK constraint error ("Succes" is misspelled)
-- EXEC etl.usp_EndRun @RunID = 1, @Status = 'Succes';

-- Clean up after looking at the results (empties the table, numbering restarts at 1)
-- TRUNCATE TABLE etl.RunLog;
