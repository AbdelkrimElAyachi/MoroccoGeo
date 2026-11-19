# Runs Phase 2 packages and the Phase 2 tests.
# Usage (PowerShell):  D:\DroughtProject\ssis\tests\run_phase2.ps1 [-WithWeather]
# Start the SQL Server service first. Expected last line: ALL PHASE 2 TESTS PASSED
param([switch]$WithWeather)

$dtexec = 'C:\Program Files\Microsoft SQL Server\170\DTS\Binn\DTExec.exe'
$root   = 'D:\DroughtProject'
$pkgs = @('03_Crops', '04_Rainfall', '05_Drought')
if ($WithWeather) { $pkgs += '06_Weather' }

foreach ($pkg in $pkgs) {
    $file = if (Test-Path "$root\ssis\DroughtETL\$pkg.dtsx") { "$root\ssis\DroughtETL\$pkg.dtsx" } else { "$root\ssis\_incoming\$pkg.dtsx" }
    Write-Host "== Package $pkg"
    & $dtexec /F $file /Rep E | Select-Object -Last 3
    if ($LASTEXITCODE -ne 0) { Write-Host "Package $pkg FAILED (see etl.RunLog)"; exit 1 }
}
Write-Host "== Tests"
sqlcmd -S localhost -E -C -W -f 65001 -i "$root\sql\tests\phase2_tests.sql"
