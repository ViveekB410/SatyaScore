$ErrorActionPreference = "Stop"
$g = "C:\Users\vivek\AppData\Local\Temp\claude\C--Users-vivek-Downloads-satyascore\d71aa683-7da1-4331-a85a-d3a2236a7da7\scratchpad\docgen2"
$env:NODE_PATH = "C:\Users\vivek\AppData\Local\Temp\claude\C--Users-vivek-Downloads-satyascore\b4965359-c236-491c-9218-9ec55611bd1a\scratchpad\docgen\node_modules"
$enc = New-Object Text.UTF8Encoding $false
$o = "$g\out"; New-Item -ItemType Directory -Force $o | Out-Null
$out = "$o\SatyaScore_Project_Report_College.docx"
# page numbers as printed (roman in the front matter, arabic from Chapter 1): wdActiveEndAdjustedPageNumber = 1
function Get-Pages($path, $keys) {
  $w = New-Object -ComObject Word.Application; $w.DisplayAlerts = 0
  try { $doc = $w.Documents.Open($path, $false, $true); $res = [ordered]@{}
    foreach ($k in $keys) { $rg = $doc.Content; $rg.Find.Text = $k.key; $rg.Find.MatchCase = $true; $rg.Find.Wrap = 0; $hit = $null
      while ($rg.Find.Execute()) { $hit = $rg.Information(1); if ($k.mode -ne "last") { break }; $rg.Collapse(0) }
      $res[$k.key] = $(if ($null -eq $hit) { "MISSING" } else { $hit }) }
    $n = $doc.ComputeStatistics(2); $doc.Close([ref]0) } finally { $w.Quit() }
  return @($res, $n) }
[IO.File]::WriteAllText("$g\pages_v3.json", "{}", $enc)
Push-Location $g; node college_report_v3.js $out; if ($LASTEXITCODE) { throw "node failed" }; Pop-Location
$keys = Get-Content "$g\keys_v3.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$p1, $n1 = Get-Pages $out $keys
for ($i = 0; $i -lt 4; $i++) {
  [IO.File]::WriteAllText("$g\pages_v3.json", ($p1 | ConvertTo-Json), $enc)
  Push-Location $g; node college_report_v3.js $out | Out-Null; Pop-Location
  $p2, $n2 = Get-Pages $out $keys
  $diff = @($keys | Where-Object { "$($p1[$_.key])" -ne "$($p2[$_.key])" })
  if (-not $diff.Count) { break }
  $p1 = $p2
}
$miss = @($keys | Where-Object { $p2[$_.key] -eq "MISSING" } | ForEach-Object { $_.key })
"pages: $n2 | passes: $($i + 2) | contents stable: " + $(if ($diff.Count) { "NO" } else { "yes" }) + " | missing: " + $(if ($miss.Count) { $miss -join ", " } else { "none" })
$w = New-Object -ComObject Word.Application; $w.DisplayAlerts = 0
try { $doc = $w.Documents.Open($out, $false, $true); $doc.ExportAsFixedFormat("$o\SatyaScore_Project_Report_College.pdf", 17); $doc.Close([ref]0) } finally { $w.Quit() }
"pdf exported"

