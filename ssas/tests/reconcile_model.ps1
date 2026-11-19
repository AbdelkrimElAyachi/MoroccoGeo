# Step 13 test: the SSAS model gives the same numbers as SQL (reconciliation).
# Each line asks the same question in DAX (model) and in SQL (warehouse) and compares.
# Usage (PowerShell):  D:\DroughtProject\ssas\tests\reconcile_model.ps1
# Expected last line: ALL MODEL RECONCILIATION TESTS PASSED

$dll = 'C:\Program Files\Microsoft SQL Server Management Studio 22\Release\Common7\IDE'
[void][Reflection.Assembly]::LoadFrom("$dll\Microsoft.AnalysisServices.AdomdClient.dll")
$ssas = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection 'Data Source=localhost;Catalog=DroughtModel'
$ssas.Open()

function Dax($q) {
    $cmd = $ssas.CreateCommand(); $cmd.CommandText = $q
    $r = $cmd.ExecuteReader(); $null = $r.Read(); $v = $r.GetValue(0); $r.Close(); return $v
}
function Sql($q) {
    $out = sqlcmd -S localhost -E -C -h -1 -W -Q "SET NOCOUNT ON; USE DWH_DB; $q"
    return ($out | Where-Object { $_ -and $_ -notmatch 'Changed database' } | Select-Object -First 1).Trim()
}

$tests = @(
  @{ n = 'Rows: rainfall';                 dax = 'EVALUATE ROW("v", COUNTROWS(Rainfall))';            sql = 'SELECT COUNT(*) FROM dbo.FactRainfallMonthly' },
  @{ n = 'Rows: drought index';            dax = 'EVALUATE ROW("v", COUNTROWS(Drought))';             sql = 'SELECT COUNT(*) FROM dbo.FactDroughtIndex' },
  @{ n = 'Rows: vegetation';               dax = 'EVALUATE ROW("v", COUNTROWS(Vegetation))';          sql = 'SELECT COUNT(*) FROM dbo.FactVegetationMonthly' },
  @{ n = 'Rows: reservoirs';               dax = 'EVALUATE ROW("v", COUNTROWS(Reservoir))';           sql = 'SELECT COUNT(*) FROM dbo.FactReservoirMonthly' },
  @{ n = 'Rows: crop production';          dax = "EVALUATE ROW(""v"", COUNTROWS('Crop Production'))"; sql = 'SELECT COUNT(*) FROM dbo.FactCropProduction' },
  @{ n = 'Population 2024';                dax = 'EVALUATE ROW("v", [Population 2024])';              sql = "SELECT SUM(Pop2024) FROM dbo.DimGeography WHERE GeoLevel = 'Province'" },
  @{ n = 'Wheat production 2024 (t)';      dax = "EVALUATE ROW(""v"", ROUND(CALCULATE([Wheat Production (t)], 'Date'[Year] = 2024), 0))";
                                           sql = "SELECT CAST(ROUND(ProductionT, 0) AS BIGINT) FROM dbo.FactCropProduction f JOIN dbo.DimCrop c ON c.CropKey = f.CropKey WHERE c.FaoItemCode = 15 AND f.[Year] = 2024" },
  @{ n = 'Provinces in drought, Aug 2022'; dax = "EVALUATE ROW(""v"", CALCULATE([Provinces in Drought], 'Date'[Year] = 2022, 'Date'[Month] = 8))";
                                           sql = 'SELECT COUNT(*) FROM dbo.FactDroughtIndex WHERE SpiScale = 12 AND DateKey = 20220801 AND SpiValue <= -1' },
  @{ n = 'People in drought, Aug 2022';    dax = "EVALUATE ROW(""v"", CALCULATE([People in Drought], 'Date'[Year] = 2022, 'Date'[Month] = 8))";
                                           sql = 'SELECT SUM(g.Pop2024) FROM dbo.FactDroughtIndex f JOIN dbo.DimGeography g ON g.GeographyKey = f.GeographyKey WHERE f.SpiScale = 12 AND f.DateKey = 20220801 AND f.SpiValue <= -1' },
  @{ n = 'Settat rain 2024 (mm, 1 dec)';   dax = "EVALUATE ROW(""v"", ROUND(CALCULATE([Rain (mm)], 'Date'[Year] = 2024, Province[ProvinceShort] = ""Settat""), 1))";
                                           sql = "SELECT CAST(ROUND(SUM(f.RainMm), 1) AS DECIMAL(9,1)) FROM dbo.FactRainfallMonthly f JOIN dbo.DimGeography g ON g.GeographyKey = f.GeographyKey WHERE g.ProvinceShort = N'Settat' AND f.DateKey BETWEEN 20240101 AND 20241201" },
  @{ n = 'Settat rain % normal 2024 (1 dec)'; dax = "EVALUATE ROW(""v"", ROUND(100 * CALCULATE([Rain % of Normal], 'Date'[Year] = 2024, Province[ProvinceShort] = ""Settat""), 1))";
                                           sql = "SELECT CAST(ROUND(100.0 * SUM(f.RainMm) / SUM(f.NormalMm), 1) AS DECIMAL(9,1)) FROM dbo.FactRainfallMonthly f JOIN dbo.DimGeography g ON g.GeographyKey = f.GeographyKey WHERE g.ProvinceShort = N'Settat' AND f.DateKey BETWEEN 20240101 AND 20241201" },
  @{ n = 'Al Massira fill index Apr 2024 (1 dec)'; dax = "EVALUATE ROW(""v"", ROUND(100 * CALCULATE([Fill Index], 'Date'[Year] = 2024, 'Date'[Month] = 4, Dam[DamName] = ""Barrage Al Massira""), 1))";
                                           sql = "SELECT CAST(ROUND(100.0 * f.WaterKm2 / d.MaxWaterKm2, 1) AS DECIMAL(5,1)) FROM dbo.FactReservoirMonthly f JOIN dbo.DimDam d ON d.DamKey = f.DamKey WHERE d.DamName = N'Barrage Al Massira' AND f.DateKey = 20240401" },
  @{ n = 'Settat NDVI farmland Mar 2021 (3 dec)'; dax = "EVALUATE ROW(""v"", ROUND(CALCULATE([NDVI Farmland], 'Date'[Year] = 2021, 'Date'[Month] = 3, Province[ProvinceShort] = ""Settat""), 3))";
                                           sql = "SELECT CAST(ROUND(f.NdviCrop, 3) AS DECIMAL(6,3)) FROM dbo.FactVegetationMonthly f JOIN dbo.DimGeography g ON g.GeographyKey = f.GeographyKey WHERE g.ProvinceShort = N'Settat' AND f.DateKey = 20210301" }
)

$fail = 0
foreach ($t in $tests) {
    try { $d = Dax $t.dax } catch { $d = "DAX ERROR: $($_.Exception.InnerException.Message)" }
    $s = Sql $t.sql
    $ok = ("$d" -ne '' -and [double]::TryParse("$d", [ref]$null) -and [double]::TryParse("$s", [ref]$null) -and [math]::Abs([double]$d - [double]$s) -lt 0.0001)
    if (-not $ok) { $fail++ }
    Write-Host ("{0,-40} model={1,-14} sql={2,-14} {3}" -f $t.n, $d, $s, $(if ($ok) { 'PASS' } else { 'FAIL' }))
}
$ssas.Close()
if ($fail -eq 0) { Write-Host 'ALL MODEL RECONCILIATION TESTS PASSED' } else { Write-Host "$fail TEST(S) FAILED" }
