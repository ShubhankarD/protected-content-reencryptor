<#
Query SharePoint sites using PnP.PowerShell with credentials from a .env file.

Behavior:
- Loads key/value pairs from a .env file (default .env in cwd).
- Tries auth strategies in this order:
  1) ACCESS_TOKEN (Connect-PnPOnline -AccessToken) — token must target SharePoint resource.
  2) CLIENT_ID + CLIENT_SECRET + TENANT_ID -> app-only Connect-PnPOnline to admin site.
  3) CLIENT_ID only -> interactive Connect-PnPOnline to site URL (delegated).
- Connects to the admin site (derives admin URL from SITE_URL if ADMIN_URL not provided).
- Calls Get-PnPTenantSite to list sites (requires tenant admin/app permissions).
- Emits a single JSON object on STDOUT with success, count and up-to-first-200 sites.

Usage:
pwsh -File .\\scripts\\query_pnponline.ps1 -EnvPath .env -SiteUrl 'https://contoso.sharepoint.com'
#>
param(
    [string]$EnvPath = ".env",
    [string]$SiteUrl = ""
)

function Load-DotEnv([string]$path) {
    if (-not (Test-Path $path)) { return @{} }
    $pairs = @{}
    Get-Content $path | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.TrimStart().StartsWith("#")) { return }
        if ($line -match '^\s*([^=]+)\s*=\s*(.*)$') {
            $k = $matches[1].Trim()
            $v = $matches[2].Trim()
            # strip optional surrounding quotes
            if ($v.StartsWith('"') -and $v.EndsWith('"') -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
                $v = $v.Substring(1,$v.Length-2)
            }
            $pairs[$k] = $v
        }
    }
    return $pairs
}

try {
    $envPairs = Load-DotEnv -path $EnvPath
    foreach ($k in $envPairs.Keys) {
        # don't overwrite existing environment variables if already set in the shell
        $existing = [Environment]::GetEnvironmentVariable($k, "Process")
        if (-not [string]::IsNullOrEmpty($existing)) { continue }
        # set for this process only
        [Environment]::SetEnvironmentVariable($k, $envPairs[$k], "Process")
    }

    if (-not $SiteUrl) {
        if ($env:SITE_URL) { $SiteUrl = $env:SITE_URL }
        elseif ($env:SHAREPOINT_SITE_URL) { $SiteUrl = $env:SHAREPOINT_SITE_URL }
        else { throw "SiteUrl not provided and not found in .env (SITE_URL or SHAREPOINT_SITE_URL)." }
    }

    # Determine admin URL if not provided
    if ($env:ADMIN_URL) { $AdminUrl = $env:ADMIN_URL }
    else {
        try {
            $u = [Uri]$SiteUrl
            if ($u.Host -match '^(?<tenant>[^.]+)\.sharepoint\.com$') {
                $AdminUrl = \"https://$($Matches.tenant)-admin.sharepoint.com\"
            } else {
                $AdminUrl = \"$($u.Scheme)://$($u.Host)\"  # fallback
            }
        } catch {
            $AdminUrl = $SiteUrl
        }
    }

    # Ensure PnP.PowerShell is available
    if (-not (Get-Command -Name Connect-PnPOnline -ErrorAction SilentlyContinue)) {
        Write-Host "PnP.PowerShell not found; installing to CurrentUser scope..." -ForegroundColor Yellow
        Install-Module -Name PnP.PowerShell -Scope CurrentUser -Force -AllowClobber -ErrorAction Stop
        Import-Module PnP.PowerShell -ErrorAction Stop
    } else {
        Import-Module PnP.PowerShell -ErrorAction Stop
    }

    $conn = $null
    $usedAuth = $null

    # 1) ACCESS_TOKEN (must be a SPO token; Graph tokens won't work for SPO REST)
    if ($env:ACCESS_TOKEN) {
        try {
            Connect-PnPOnline -Url $SiteUrl -AccessToken $env:ACCESS_TOKEN -ErrorAction Stop
            $conn = Get-PnPConnection
            $usedAuth = "access_token"
        } catch {
            # continue to other methods
            Write-Host "Connect with ACCESS_TOKEN failed: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }

    # 2) App-only client credentials (connect to admin site)
    if (-not $conn -and $env:CLIENT_ID -and $env:CLIENT_SECRET -and $env:TENANT_ID) {
        try {
            Connect-PnPOnline -Url $AdminUrl -ClientId $env:CLIENT_ID -ClientSecret $env:CLIENT_SECRET -Tenant $env:TENANT_ID -ErrorAction Stop
            $conn = Get-PnPConnection
            $usedAuth = "client_credentials_admin"
        } catch {
            Write-Host "App-only connect failed: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }

    # 3) Interactive delegated (public client)
    if (-not $conn -and $env:CLIENT_ID) {
        try {
            Connect-PnPOnline -Url $SiteUrl -ClientId $env:CLIENT_ID -Interactive -ErrorAction Stop
            $conn = Get-PnPConnection
            $usedAuth = "interactive_delegated"
        } catch {
            Write-Host "Interactive connect failed: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }

    if (-not $conn) { throw "No successful PnP connection established. Provide ACCESS_TOKEN or CLIENT_ID/CLIENT_SECRET/TENANT_ID or CLIENT_ID + interactive." }

    # If we connected to the admin site, use Get-PnPTenantSite to enumerate all sites.
    $sites = @()
    $isAdminConnection = $conn.Url -like "*-admin.sharepoint.com*"

    if ($isAdminConnection) {
        # Retrieve tenant sites (may be large). Limit how many we include in JSON.
        $tenantSites = Get-PnPTenantSite -Detailed -ErrorAction Stop
        $sites = $tenantSites | Select-Object @{n='Url';e={$_.Url}}, @{n='Title';e={$_.Title}}, @{n='Template';e={$_.Template}}, @{n='Owner';e={$_.Owner}} 
    } else {
        # Non-admin connection: return the connected site and optionally subsites
        $root = Get-PnPSite -ErrorAction Stop
        $sites = @([PSCustomObject]@{ Url = $conn.Url; Title = $root.Title; Template = $root.Template; Owner = $null })
    }

    $count = ($sites | Measure-Object).Count
    $sample = $sites | Select-Object -First 200

    $out = [PSCustomObject]@{
        success = $true
        usedAuth = $usedAuth
        connectionUrl = $conn.Url
        siteCount = $count
        sampleSites = $sample
    }
    $json = $out | ConvertTo-Json -Depth 6
    Write-Output $json
    exit 0
}
catch {
    $errObj = [PSCustomObject]@{
        success = $false
        error = $_.Exception.Message
        details = $_ | Out-String
    }
    $errObj | ConvertTo-Json -Depth 3
    exit 1
}