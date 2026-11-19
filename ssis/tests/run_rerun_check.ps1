# Phase 3 check: safe re-runs (idempotence).
# Runs every loaded package TWICE and checks that the second run changes nothing:
#   - same number of rows in every table
#   - etl.LoadAudit for the second run: 0 rows inserted, 0 rows updated
# Usage (PowerShell):  D:\DroughtProject\ssis\tests\run_rerun_check.ps1
# Start SQL Server first. Takes ~20-30 min (CHIRPS recomputation, Earth Engine calls).

$dtexec = 'C:\Program Files\Microsoft SQL Server\170\DTS\Binn\DTExec.exe'
$dir    = 'D:\DroughtProject\ssis\DroughtETL'
$pkgs   = '01_Boundaries', '02_Geography', '03_Crops', '04_Rainfall', '05_Drought', '07_Vegetation', '08_Reservoirs'
if ((Get-ChildItem D:\DroughtProject\raw\openmeteo -Filter *.csv).Count -eq 75) { $pkgs += '06_Weather' }

$countSql = "SET NOCOUNT ON; SELECT t.name + '=' + CAST(SUM(p.rows) AS VARCHAR(20)) FROM DWH_DB.sys.tables t JOIN DWH_DB.sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0,1) WHERE t.schema_id = 1 GROUP BY t.name ORDER BY t.name;"

function Run-All($label) {
    foreach ($p in $pkgs) {
        $t = Get-Date
        & $dtexec /F "$dir\$p.dtsx" /Rep E | Out-Null
        $code = $LASTEXITCODE
        Write-Host ("  {0} {1,-14} exit {2} ({3}s)" -f $label, $p, $code, [int]((Get-Date) - $t).TotalSeconds)
        if ($code -ne 0) { Write-Host "  FAILED: see DWH_DB.etl.RunLog"; exit 1 }
    }
}

Write-Host "== Run 1"
Run-All "run1"
$after1 = sqlcmd -S localhost -E -C -h -1 -W -Q $countSql
$mark = sqlcmd -S localhost -E -C -h -1 -W -Q "SET NOCOUNT ON; SELECT ISNULL(MAX(AuditID), 0) FROM DWH_DB.etl.LoadAudit;"

Write-Host "== Run 2 (must change nothing)"
Run-All "run2"
$after2 = sqlcmd -S localhost -E -C -h -1 -W -Q $countSql

Write-Host "== Row counts after run 1 vs run 2"
$same = $true
for ($i = 0; $i -lt $after1.Count; $i++) {
    $flag = if ($after1[$i] -eq $after2[$i]) { "same" } else { $same = $false; "DIFFERENT" }
    Write-Host ("  {0,-40} {1,-40} {2}" -f $after1[$i], $after2[$i], $flag)
}

Write-Host "== Load audit of run 2 (expected: 0 inserted, 0 updated)"
sqlcmd -S localhost -E -C -W -Q "SET NOCOUNT ON; SELECT TableName, SourceRows, RowsInserted, RowsUpdated, RowsUnchanged FROM DWH_DB.etl.LoadAudit WHERE AuditID > $($mark.Trim()) ORDER BY AuditID;"
$changed = sqlcmd -S localhost -E -C -h -1 -W -Q "SET NOCOUNT ON; SELECT SUM(RowsInserted + RowsUpdated) FROM DWH_DB.etl.LoadAudit WHERE AuditID > $($mark.Trim());"

if ($same -and [int]$changed.Trim() -eq 0) { Write-Host "RE-RUN CHECK PASSED: second run changed nothing" }
else { Write-Host "RE-RUN CHECK FAILED: rows changed on the second run = $($changed.Trim())" }
