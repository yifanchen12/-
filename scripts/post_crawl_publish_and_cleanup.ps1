param(
    [int]$CrawlPid,
    [string]$Branch = "main",
    [int]$PartSizeMB = 90,
    [switch]$CleanupLocalData
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $ProjectRoot "logs"
$LogPath = Join-Path $LogDir "post_crawl_publish.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
}

function Split-File {
    param(
        [string]$InputPath,
        [string]$OutputDirectory,
        [int64]$PartSizeBytes
    )

    New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
    $buffer = New-Object byte[] (1024 * 1024)
    $input = [System.IO.File]::OpenRead($InputPath)
    try {
        $part = 1
        while ($input.Position -lt $input.Length) {
            $partPath = Join-Path $OutputDirectory ("{0}.part{1:D3}" -f (Split-Path -Leaf $InputPath), $part)
            $output = [System.IO.File]::Create($partPath)
            try {
                $written = 0L
                while ($written -lt $PartSizeBytes -and $input.Position -lt $input.Length) {
                    $toRead = [Math]::Min($buffer.Length, $PartSizeBytes - $written)
                    $read = $input.Read($buffer, 0, [int]$toRead)
                    if ($read -le 0) { break }
                    $output.Write($buffer, 0, $read)
                    $written += $read
                }
            }
            finally {
                $output.Dispose()
            }
            $part += 1
        }
    }
    finally {
        $input.Dispose()
    }
}

Write-Log "Waiting for crawler PID $CrawlPid."
if (Get-Process -Id $CrawlPid -ErrorAction SilentlyContinue) {
    Wait-Process -Id $CrawlPid
}
Write-Log "Crawler process finished or is no longer running."

$DbPath = Join-Path $ProjectRoot "data\bupt_library.sqlite3"
$ExcelPath = Join-Path $ProjectRoot "output\bupt_library_holdings.xlsx"
if (-not (Test-Path $DbPath)) { throw "Missing SQLite database: $DbPath" }
if (-not (Test-Path $ExcelPath)) { throw "Missing Excel workbook: $ExcelPath" }

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$TempRoot = Join-Path $env:TEMP "bupt-library-crawl-$Stamp"
$PackageDir = Join-Path $TempRoot "package"
$ArtifactDir = Join-Path $TempRoot "artifacts"
$CloneDir = Join-Path $TempRoot "repo"
New-Item -ItemType Directory -Force -Path $PackageDir, $ArtifactDir | Out-Null

Copy-Item -LiteralPath $DbPath -Destination (Join-Path $PackageDir "bupt_library.sqlite3") -Force
Copy-Item -LiteralPath $ExcelPath -Destination (Join-Path $PackageDir "bupt_library_holdings.xlsx") -Force

$ZipName = "bupt_library_full_crawl_$Stamp.zip"
$ZipPath = Join-Path $TempRoot $ZipName
Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $ZipPath -CompressionLevel Optimal

$PartSizeBytes = [int64]$PartSizeMB * 1024 * 1024
if ((Get-Item $ZipPath).Length -gt $PartSizeBytes) {
    Write-Log "Archive exceeds $PartSizeMB MB; splitting into parts."
    Split-File -InputPath $ZipPath -OutputDirectory $ArtifactDir -PartSizeBytes $PartSizeBytes
}
else {
    Copy-Item -LiteralPath $ZipPath -Destination (Join-Path $ArtifactDir $ZipName) -Force
}

$ManifestPath = Join-Path $ArtifactDir "README_ARTIFACTS.md"
@(
    "# Full Crawl Artifacts"
    ""
    "Generated at: $Stamp"
    ""
    "Files included in the archive:"
    ""
    "- ``bupt_library.sqlite3``"
    "- ``bupt_library_holdings.xlsx``"
    ""
    "If the archive is split into ``.partNNN`` files, reconstruct it in PowerShell:"
    ""
    "``````powershell"
    "`$output = 'bupt_library_full_crawl_$Stamp.zip'"
    "Remove-Item `$output -ErrorAction SilentlyContinue"
    "Get-ChildItem 'bupt_library_full_crawl_$Stamp.zip.part*' | Sort-Object Name | ForEach-Object {"
    "    `$in = [System.IO.File]::OpenRead(`$_.FullName)"
    "    `$out = [System.IO.File]::Open(`$output, [System.IO.FileMode]::Append)"
    "    try { `$in.CopyTo(`$out) } finally { `$in.Dispose(); `$out.Dispose() }"
    "}"
    "``````"
) | Set-Content -Path $ManifestPath -Encoding UTF8

$RepoUrl = git -C $ProjectRoot remote get-url origin
Write-Log "Cloning $RepoUrl to temporary publish checkout."
git clone $RepoUrl $CloneDir | Tee-Object -FilePath $LogPath -Append
git -C $CloneDir checkout $Branch | Tee-Object -FilePath $LogPath -Append

$TargetArtifactDir = Join-Path $CloneDir "artifacts"
New-Item -ItemType Directory -Force -Path $TargetArtifactDir | Out-Null
Copy-Item -Path (Join-Path $ArtifactDir "*") -Destination $TargetArtifactDir -Force

git -C $CloneDir add -f artifacts | Tee-Object -FilePath $LogPath -Append
git -C $CloneDir commit -m "Add full crawl artifacts $Stamp" | Tee-Object -FilePath $LogPath -Append
git -C $CloneDir push origin $Branch | Tee-Object -FilePath $LogPath -Append
Write-Log "Artifacts pushed to GitHub."

if ($CleanupLocalData) {
    Write-Log "Cleaning local data and output directories."
    Remove-Item -LiteralPath (Join-Path $ProjectRoot "data") -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $ProjectRoot "output") -Recurse -Force -ErrorAction SilentlyContinue
}

Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
Write-Log "Post-crawl publish and cleanup finished."
