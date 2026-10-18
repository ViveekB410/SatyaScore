$ErrorActionPreference = "Stop"
$g = "C:\Users\vivek\AppData\Local\Temp\claude\C--Users-vivek-Downloads-satyascore\d71aa683-7da1-4331-a85a-d3a2236a7da7\scratchpad\docgen2"
$env:NODE_PATH = "C:\Users\vivek\AppData\Local\Temp\claude\C--Users-vivek-Downloads-satyascore\b4965359-c236-491c-9218-9ec55611bd1a\scratchpad\docgen\node_modules"
$enc = New-Object Text.UTF8Encoding $false
$o = "$g\out"; New-Item -ItemType Directory -Force $o | Out-Null
$out = "$o\SatyaScore_Project_Report_v2.docx"
[IO.File]::WriteAllText("$g\pages_college.json", "{}", $enc)
Push-Location $g; node college_report.js $out; if ($LASTEXITCODE) { throw "node failed" }; Pop-Location
$keys = Get-Content "$g\keys_college.json" -Raw | ConvertFrom-Json
function Get-Pages($path) {
  $w = New-Object -ComObject Word.Application; $w.DisplayAlerts = 0
  try { $doc = $w.Documents.Open($path, $false, $true); $res = [ordered]@{}
    $sec = $doc.Sections($doc.Sections.Count)   # the chapters section (numbered from 1)
    foreach ($k in $keys) { $rg = $sec.Range; $rg.Find.Text = $k; $rg.Find.MatchCase = $true; $rg.Find.Wrap = 0
      if ($rg.Find.Execute()) { $res[$k] = $rg.Information(1) } else { $res[$k] = "MISSING" } }
    $n = $doc.ComputeStatistics(2); $doc.Close([ref]0) } finally { $w.Quit() }
  return @($res, $n) }
$p1, $n1 = Get-Pages $out
for ($i = 0; $i -lt 4; $i++) {
  [IO.File]::WriteAllText("$g\pages_college.json", ($p1 | ConvertTo-Json), $enc)
  Push-Location $g; node college_report.js $out | Out-Null; Pop-Location
  $p2, $n2 = Get-Pages $out
  $diff = @($keys | Where-Object { "$($p1[$_])" -ne "$($p2[$_])" })
  if (-not $diff.Count) { break }
  $p1 = $p2
}
$miss = @($keys | Where-Object { $p2[$_] -eq "MISSING" })
"pages: $n2 | passes: $($i + 2) | contents stable: " + $(if ($diff.Count) { "NO (" + ($diff -join ", ") + ")" } else { "yes" }) + " | missing: " + $(if ($miss.Count) { $miss -join ", " } else { "none" })
$w = New-Object -ComObject Word.Application; $w.DisplayAlerts = 0
try { $doc = $w.Documents.Open($out, $false, $true); $doc.ExportAsFixedFormat("$o\SatyaScore_Project_Report_v2.pdf", 17); $doc.Close([ref]0) } finally { $w.Quit() }
"pdf exported"
