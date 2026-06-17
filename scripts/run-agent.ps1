param(
    [Parameter(Position = 0)]
    [string]$ProductName = "Notion",

    [int]$LimitPosts = 10,
    [int]$CommentsPerPost = 3,
    [int]$SearchScrolls = -1,
    [string]$Out = "",
    [string]$Database = ""
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$webAccessCheck = "C:\Users\1\.codex\skills\web-access\scripts\check-deps.mjs"

if (-not (Test-Path -LiteralPath (Join-Path $projectRoot ".env"))) {
    throw ".env is missing. Copy .env.example to .env and fill MOONSHOT_API_KEY first."
}

if (-not (Test-Path -LiteralPath $webAccessCheck)) {
    throw "web-access check script was not found at $webAccessCheck"
}

Push-Location $projectRoot
try {
    node $webAccessCheck
    if ($LASTEXITCODE -ne 0) {
        throw "web-access dependency check failed with exit code $LASTEXITCODE"
    }

    if ([string]::IsNullOrWhiteSpace($Out)) {
        $safeName = ($ProductName -replace "[^A-Za-z0-9._-]", "-").Trim("-")
        if ([string]::IsNullOrWhiteSpace($safeName)) {
            $safeName = "reddit-pain-search"
        }
        $Out = "results/$safeName.csv"
    }

    $args = @(
        $ProductName,
        "--limit-posts",
        $LimitPosts,
        "--comments-per-post",
        $CommentsPerPost,
        "--out",
        $Out
    )

    if ($SearchScrolls -ge 0) {
        $args += @("--search-scrolls", $SearchScrolls)
    }

    if (-not [string]::IsNullOrWhiteSpace($Database)) {
        $args += @("--database", $Database)
    }

    reddit-pain-search @args
    if ($LASTEXITCODE -ne 0) {
        throw "reddit-pain-search failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
