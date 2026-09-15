# Render the stripped decks to the 1366x720 backgrounds the HMI stage expects.
#
#   powershell -File render_slides.ps1 323-1 324-1 328-2
#
# Run from the work directory: reads .\stripped\<name>.pptx and writes
# .\stripped\screen-<name>.png.  Exports at 2x and downsamples, because PowerPoint's
# own 1366x720 export aliases the thin instrument lines badly.
#
# The stage is 1366x720 but a 16:9 slide is 1366x768, so this export is deliberately
# ANISOTROPIC -- the same squash build_overlays.py applies when it maps EMU to stage
# pixels, and the same one sizeIcon() undoes with scaleX(SLIDE_RX) for rotated icons.
# Change one and you must change all three.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Names)

if (-not $Names) { Write-Error "usage: render_slides.ps1 <slide-name> [...]"; exit 1 }

$work = (Get-Location).Path
$app = New-Object -ComObject PowerPoint.Application
foreach ($n in $Names) {
  $src = Join-Path $work "stripped\$n.pptx"
  if (-not (Test-Path $src)) { Write-Error "missing $src (run strip_slides.py first)"; continue }
  $pres = $app.Presentations.Open($src, $true, $false, $false)
  $pres.Slides.Item(1).Export((Join-Path $work "stripped\$n-2x.png"), "PNG", 2732, 1440)
  $pres.Close()
}
$app.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null

Add-Type -AssemblyName System.Drawing
foreach ($n in $Names) {
  $big = Join-Path $work "stripped\$n-2x.png"
  if (-not (Test-Path $big)) { continue }
  $src = [System.Drawing.Image]::FromFile($big)
  $bmp = New-Object System.Drawing.Bitmap 1366, 720
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
  $g.DrawImage($src, (New-Object System.Drawing.Rectangle 0, 0, 1366, 720))
  $g.Dispose(); $src.Dispose()
  $bmp.Save((Join-Path $work "stripped\screen-$n.png"), [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
  Remove-Item $big
  "rendered screen-$n.png"
}
