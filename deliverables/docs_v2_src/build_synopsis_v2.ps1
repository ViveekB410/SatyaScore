$ErrorActionPreference = "Stop"
$g = "C:\Users\vivek\AppData\Local\Temp\claude\C--Users-vivek-Downloads-satyascore\d71aa683-7da1-4331-a85a-d3a2236a7da7\scratchpad\docgen2"
$env:NODE_PATH = "C:\Users\vivek\AppData\Local\Temp\claude\C--Users-vivek-Downloads-satyascore\b4965359-c236-491c-9218-9ec55611bd1a\scratchpad\docgen\node_modules"
$enc = New-Object Text.UTF8Encoding $false
$o = "$g\out"; New-Item -ItemType Directory -Force $o | Out-Null
$out = "$o\SatyaScore_Synopsis_v2.docx"

function Export-Pdf($docx, $pdf) {
  $w = New-Object -ComObject Word.Application; $w.DisplayAlerts = 0
  try { $d = $w.Documents.Open($docx, $false, $true); $n = $d.ComputeStatistics(2); $d.ExportAsFixedFormat($pdf, 17); $d.Close([ref]0) } finally { $w.Quit() }
  return $n
}
# index page numbers: absolute pages; the last occurrence of each heading is the body, not the index
function Get-Pages($path, $keys) {
  $w = New-Object -ComObject Word.Application; $w.DisplayAlerts = 0
  try { $doc = $w.Documents.Open($path, $false, $true); $res = [ordered]@{}
    foreach ($k in $keys) { $rg = $doc.Content; $rg.Find.Text = $k; $rg.Find.MatchCase = $true; $rg.Find.Wrap = 0; $last = $null
      while ($rg.Find.Execute()) { $last = $rg.Information(3); $rg.Collapse(0) }
      $res[$k] = $(if ($null -eq $last) { "MISSING" } else { $last }) }
    $n = $doc.ComputeStatistics(2); $doc.Close([ref]0) } finally { $w.Quit() }
  return @($res, $n) }
[IO.File]::WriteAllText("$g\pages_synopsis.json", "{}", $enc)
Push-Location $g; node synopsis_updated.js $out; if ($LASTEXITCODE) { throw "node failed" }; Pop-Location
$keys = Get-Content "$g\keys_synopsis.json" -Raw | ConvertFrom-Json
$p1, $n1 = Get-Pages $out $keys
for ($i = 0; $i -lt 4; $i++) {
  [IO.File]::WriteAllText("$g\pages_synopsis.json", ($p1 | ConvertTo-Json), $enc)
  Push-Location $g; node synopsis_updated.js $out | Out-Null; Pop-Location
  $p2, $n2 = Get-Pages $out $keys
  $diff = @($keys | Where-Object { "$($p1[$_])" -ne "$($p2[$_])" }); if (-not $diff.Count) { break }; $p1 = $p2
}
$miss = @($keys | Where-Object { $p2[$_] -eq "MISSING" })
"SatyaScore_Synopsis_v2: $n2 pages | index stable: " + $(if ($diff.Count) { "NO" } else { "yes" }) + " | missing: " + $(if ($miss.Count) { $miss -join ", " } else { "none" })
$null = Export-Pdf $out "$o\SatyaScore_Synopsis_v2.pdf"
"done"
