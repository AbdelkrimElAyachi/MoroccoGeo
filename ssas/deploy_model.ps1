# Deploys ssas/Model.bim to the local Analysis Services server (database "DroughtModel")
# and processes it (loads the data from DWH_DB).
# Usage (PowerShell):  D:\DroughtProject\ssas\deploy_model.ps1
# Start SQL Server and Analysis Services first.

$ErrorActionPreference = 'Stop'
$dll = 'C:\Program Files\Microsoft SQL Server Management Studio 22\Release\Common7\IDE'
foreach ($n in 'Microsoft.AnalysisServices.Core.dll', 'Microsoft.AnalysisServices.dll',
               'Microsoft.AnalysisServices.Tabular.dll', 'Microsoft.AnalysisServices.Tabular.Json.dll') {
    [void][Reflection.Assembly]::LoadFrom("$dll\$n")
}

$bim  = Get-Content 'D:\DroughtProject\ssas\Model.bim' -Raw -Encoding UTF8
$name = ($bim | ConvertFrom-Json).name

$server = New-Object Microsoft.AnalysisServices.Tabular.Server
$server.Connect('Data Source=localhost')

function Run-Tmsl($label, $tmsl) {
    $t = Get-Date
    $results = $server.Execute($tmsl)
    $errors = @()
    foreach ($r in $results) { foreach ($m in $r.Messages) { $errors += $m.Description } }
    if ($errors.Count) { Write-Host "$label FAILED:"; $errors | ForEach-Object { Write-Host "  $_" }; exit 1 }
    Write-Host ("{0} OK ({1}s)" -f $label, [int]((Get-Date) - $t).TotalSeconds)
}

Run-Tmsl "Deploy"  ('{"createOrReplace":{"object":{"database":"' + $name + '"},"database":' + $bim + '}}')
Run-Tmsl "Process" ('{"refresh":{"type":"full","objects":[{"database":"' + $name + '"}]}}')

$server.Disconnect(); $server.Connect('Data Source=localhost')     # reload the database list
$db = $server.Databases.GetByName($name)
Write-Host "Database $name, state: $($db.State), last processed: $($db.LastProcessed)"
foreach ($tbl in $db.Model.Tables) {
    $p = $tbl.Partitions[0]
    Write-Host ("  {0,-18} {1,2} measures  partition state: {2}" -f $tbl.Name, $tbl.Measures.Count, $p.State)
}
$server.Disconnect()
