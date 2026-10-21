# Build a SHA-256 manifest of a PlayStation 3 disc tree.
#
# Usage (on the machine that holds the optical drive):
#   powershell -File disc_manifest.ps1 -Root E:\ -Out C:\rac-disc-manifest.tsv
#
# The output is a tab separated file: sha256, size, relative path.
# Paths are relative to -Root and use forward slashes.

param(
    [Parameter(Mandatory = $true)][string]$Root,
    [Parameter(Mandatory = $true)][string]$Out
)

$ErrorActionPreference = 'Stop'
$rootFull = (Resolve-Path -LiteralPath $Root).Path.TrimEnd('\')
$lines = New-Object System.Collections.Generic.List[string]

$files = Get-ChildItem -LiteralPath $rootFull -Recurse -Force -File | Sort-Object FullName
foreach ($file in $files) {
    $rel = $file.FullName.Substring($rootFull.Length).TrimStart('\').Replace('\', '/')
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $lines.Add("$hash`t$($file.Length)`t$rel")
    if ($lines.Count % 500 -eq 0) {
        Set-Content -LiteralPath $Out -Value $lines -Encoding UTF8
    }
}

Set-Content -LiteralPath $Out -Value $lines -Encoding UTF8
"DONE $($lines.Count) files -> $Out"
