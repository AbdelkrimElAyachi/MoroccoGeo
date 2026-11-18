# Runs Phase 1 end to end and then the Phase 1 tests.
# Usage (PowerShell):  D:\DroughtProject\ssis\tests\run_phase1.ps1
# Start the SQL Server service first (it is on Manual startup).
# Expected last line: ALL PHASE 1 TESTS PASSED

$dtexec = 'C:\Program Files\Microsoft SQL Server\170\DTS\Binn\DTExec.exe'
$root   = 'D:\DroughtProject'
# packages live in the Visual Studio project; fall back to the incoming folder
$pkgDir = if (Test-Path "$root\ssis\DroughtETL\01_Boundaries.dtsx") { "$root\ssis\DroughtETL" } else { "$root\ssis\_incoming" }

foreach ($pkg in '01_Boundaries', '02_Geography') {
    Write-Host "== Package $pkg"
    & $dtexec /F "$pkgDir\$pkg.dtsx" /Rep E | Select-Object -Last 3
    if ($LASTEXITCODE -ne 0) { Write-Host "Package $pkg FAILED (see etl.RunLog)"; exit 1 }
}

Write-Host "== DimDate"
sqlcmd -S localhost -E -C -b -f 65001 -i "$root\sql\06_dim_date.sql" | Select-Object -Last 2

Write-Host "== Tests"
sqlcmd -S localhost -E -C -W -f 65001 -i "$root\sql\tests\phase1_tests.sql"
