$ErrorActionPreference = 'Stop'
$folder = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $folder
$partSize = 2L * 1024 * 1024 * 1024
$bufferSize = 1024 * 1024
$parts1 = @(Get-ChildItem -LiteralPath $folder -File | Where-Object { $_.Name -like 'icopyx-emergency-*.img.gz.001' })
if ($parts1.Count -ne 1) { throw "Expected exactly one *.img.gz.001 in $folder (found $($parts1.Count))." }
$first = $parts1[0].Name
$stem = $first.Substring(0, $first.Length - 4)
$output = Join-Path $folder $stem
if (Test-Path -LiteralPath $output) { throw "Output already exists: $stem" }
$prefix = [System.Text.RegularExpressions.Regex]::Escape($stem) + '\.(\d{3})$'
$parts = @(Get-ChildItem -LiteralPath $folder -File | Where-Object { $_.Name -match $prefix } | Sort-Object Name)
if ($parts.Count -lt 1 -or $parts.Count -gt 999) { throw 'Invalid number of parts.' }
for ($i = 0; $i -lt $parts.Count; $i++) {
    $expected = ('{0}.{1:000}' -f $stem, ($i + 1))
    if ($parts[$i].Name -cne $expected) { throw "Missing or unexpected part: expected $expected" }
    if ($parts[$i].Length -le 0 -or $parts[$i].Length -gt $partSize) { throw "Invalid part size: $expected" }
    if ($i -lt $parts.Count - 1 -and $parts[$i].Length -ne $partSize) { throw "Incomplete part: $expected" }
}
if (@(Get-ChildItem -LiteralPath $folder -File | Where-Object { $_.Name -like "$stem.*.part" }).Count -gt 0) {
    throw 'Unfinished .part files detected. Backup was not completed.'
}
$total = [long](($parts | Measure-Object -Property Length -Sum).Sum)
$free = (Get-Item -LiteralPath $folder).PSDrive.Free
if ($null -ne $free -and $free -lt ($total + 256MB)) { throw 'Not enough free space to combine image.' }
$temp = $output + '.combining'
if (Test-Path -LiteralPath $temp) { throw "Temporary output already exists: $temp" }
$buffer = New-Object byte[] $bufferSize
$target = $null
try {
    $target = [System.IO.File]::Open($temp, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
    foreach ($part in $parts) {
        Write-Host "Combining $($part.Name) ..."
        $source = [System.IO.File]::OpenRead($part.FullName)
        try {
            while (($count = $source.Read($buffer, 0, $buffer.Length)) -gt 0) {
                $target.Write($buffer, 0, $count)
            }
        } finally { $source.Dispose() }
    }
    $target.Flush()
} finally { if ($null -ne $target) { $target.Dispose() } }
if ((Get-Item -LiteralPath $temp).Length -ne $total) { throw 'Merged size mismatch.' }
Write-Host 'Verifying gzip by streaming decompression (may take several minutes)...'
$inputFile = [System.IO.File]::OpenRead($temp)
$gzip = $null
try {
    $gzip = New-Object System.IO.Compression.GZipStream($inputFile, [System.IO.Compression.CompressionMode]::Decompress)
    $rawBytes = 0L
    while (($count = $gzip.Read($buffer, 0, $buffer.Length)) -gt 0) { $rawBytes += $count }
} finally {
    if ($null -ne $gzip) { $gzip.Dispose() } else { $inputFile.Dispose() }
}
if ($rawBytes -lt 1) { throw 'Gzip image is empty.' }
# The original source card had 15,978,201,088 bytes; do not hard-code
# that value for other cards. Gzip CRC/trailer is checked by decompressor.
Move-Item -LiteralPath $temp -Destination $output
Write-Host "SUCCESS: $stem"
Write-Host "Compressed bytes: $total; decompressed bytes: $rawBytes"
Write-Host 'Write this IMG.GZ with USBImager to a spare microSD.'
