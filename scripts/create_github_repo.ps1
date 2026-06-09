param(
    [string]$RepoName = "bupt-library-crawler",
    [string]$Visibility = "private",
    [string]$Description = "Crawler and Excel exporter for BUPT Library OPAC holdings"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) is not installed."
}

gh auth status
gh repo create $RepoName --source . --remote origin --$Visibility --description $Description --push

