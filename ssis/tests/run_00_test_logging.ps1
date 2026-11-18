# Runs the Phase 0 SSIS test package twice (success, then forced failure)
# and shows the result in DWH_DB.etl.RunLog.
# Usage (PowerShell):  D:\DroughtProject\ssis\tests\run_00_test_logging.ps1
# Expected: one "Success" row and one "Failed" row with the error text.

$dtexec = 'C:\Program Files\Microsoft SQL Server\170\DTS\Binn\DTExec.exe'
$pkg    = 'D:\DroughtProject\ssis\DroughtETL\00_Test_Logging.dtsx'

Write-Host "TEST 1: success path"
& $dtexec /F $pkg /Rep E | Select-Object -Last 5
Write-Host "exit code: $LASTEXITCODE (expected 0)"

Write-Host "TEST 2: forced failure path"
& $dtexec /F $pkg /Set '\Package.Variables[User::ForceFailure].Properties[Value];True' /Rep E | Select-Object -Last 5
Write-Host "exit code: $LASTEXITCODE (expected 1)"

Write-Host "Last 2 rows of etl.RunLog:"
sqlcmd -S localhost -E -C -W -Q "SET NOCOUNT ON; SELECT TOP 2 RunID, PackageName, Status, LEFT(ErrorMessage,80) AS ErrorMessage FROM DWH_DB.etl.RunLog ORDER BY RunID DESC;"
