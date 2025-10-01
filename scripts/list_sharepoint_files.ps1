<#
.SYNOPSIS
	List SharePoint sites (and optionally lists) using an Azure AD app registration (client credentials).

DESCRIPTION
	This script performs the OAuth2 client credentials flow against Azure AD to acquire a Microsoft Graph
	token and then calls Microsoft Graph to enumerate SharePoint sites. Optionally it will list the
	lists for each site.

USAGE
	pwsh.exe -File .\scripts\list_sharepoint_files.ps1 -TenantId <tenant> -ClientId <id> -ClientSecret <secret>
	pwsh.exe -File .\scripts\list_sharepoint_files.ps1 -Search "contoso" -ListLists

PARAMETERS
	-TenantId      Azure AD tenant id (or set AZURE_TENANT_ID env var)
	-ClientId      App registration client id (or set AZURE_CLIENT_ID env var)
	-ClientSecret  App registration client secret (or set AZURE_CLIENT_SECRET env var)
	-Search        Optional search term for sites (defaults to '*')
	-ListLists     If present, the script will fetch lists for each site found

NOTES
	The app registration must have the appropriate application permissions (for example: Sites.Read.All
	or Sites.FullControl.All) and the permissions must be granted by an administrator.
#>
param(
	[Parameter(Mandatory=$false)] [string]$TenantId = $null,
	[Parameter(Mandatory=$false)] [string]$ClientId = $null,
	[Parameter(Mandatory=$false)] [string]$ClientSecret = $null,
	[Parameter(Mandatory=$false)] [string]$AdminUrl = $null,
	[Parameter(Mandatory=$false)] [string]$Search = "*",
	[switch]$ListLists,
	[switch]$AutoInstallModule,
	[switch]$DryRun
)


function Import-DotEnv {
	param(
		[Parameter(Mandatory=$true)] [string]$Path,
		[switch]$Force
	)

	if (-not (Test-Path $Path)) { return }

	Write-Host "Loading environment variables from: $Path"
	$lines = Get-Content -Raw -Path $Path -ErrorAction SilentlyContinue
	if (-not $lines) { return }
	$count = 0
	foreach ($line in $lines -split "`n") {
		$l = $line.Trim()
		if ($l -eq '' -or $l.StartsWith('#')) { continue }
		$m = [regex]::Match($l, '^[\s]*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$')
		if ($m.Success) {
			$key = $m.Groups[1].Value
			$val = $m.Groups[2].Value.Trim()
			# Remove surrounding quotes
			if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
				$val = $val.Substring(1,$val.Length-2)
			}
			# Unescape common sequences
			$val = $val -replace '\\n', "`n" -replace '\\r', "`r"

			# assign if Force OR the env var is not set/empty
			$existing = [System.Environment]::GetEnvironmentVariable($key, 'Process')
			if ($Force -or [string]::IsNullOrEmpty($existing)) {
				[System.Environment]::SetEnvironmentVariable($key, $val, 'Process')
				$count++
			}
			else {
				# variable already present and Force not set - leave it
			}
		}
	}
	Write-Host "Imported $count variables from $Path"
}

# Auto-load .env from workspace (current directory) or script folder so VS Code Run picks up values
$candidatePaths = @("$PWD\.env", "$PSScriptRoot\.env")
foreach ($p in $candidatePaths) {
	if (Test-Path $p) { Import-DotEnv -Path $p -Force:$false; break }
}

 # If parameters weren't provided via the command line, pick them up from environment variables (.env loaded above)
if (-not $TenantId) {
	if ($env:AZURE_TENANT_ID) { $TenantId = $env:AZURE_TENANT_ID }
	elseif ($env:TENANT_ID) { $TenantId = $env:TENANT_ID }
	elseif ($env:AUTHORITY) {
		$m = [regex]::Match($env:AUTHORITY, 'login.microsoftonline.com/([^/]+)')
		if ($m.Success) { $TenantId = $m.Groups[1].Value }
	}
}

if (-not $ClientId) {
	if ($env:AZURE_CLIENT_ID) { $ClientId = $env:AZURE_CLIENT_ID }
	elseif ($env:CLIENT_ID) { $ClientId = $env:CLIENT_ID }
}

if (-not $ClientSecret) {
	if ($env:AZURE_CLIENT_SECRET) { $ClientSecret = $env:AZURE_CLIENT_SECRET }
	elseif ($env:CLIENT_SECRET) { $ClientSecret = $env:CLIENT_SECRET }
	elseif ($env:PASSWORD) { $ClientSecret = $env:PASSWORD }
}

if (-not $AdminUrl) {
	if ($env:ADMIN_URL) { $AdminUrl = $env:ADMIN_URL }
	elseif ($env:SHAREPOINT_ADMIN_URL) { $AdminUrl = $env:SHAREPOINT_ADMIN_URL }
	elseif ($env:SHAREPOINT_SITE) {
		# try to infer admin URL from site host
		$m = [regex]::Match($env:SHAREPOINT_SITE, 'https?://([^.]+)\.sharepoint\.com')
		if ($m.Success) { $AdminUrl = "https://$($m.Groups[1].Value)-admin.sharepoint.com" }
	}
}

if (($Search -eq $null -or $Search -eq '') -and $env:SEARCH) { $Search = $env:SEARCH }

function Prompt-ForSecretIfNeeded {
	param([string]$Value)
	if (-not $Value) {
		$s = Read-Host -Prompt 'Client secret (will be hidden)' -AsSecureString
		return [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
	}
	return $Value
}

if (-not $TenantId) {
	Write-Error "TenantId not provided. Provide -TenantId or set AZURE_TENANT_ID environment variable."
	exit 2
}

if (-not $ClientId) {
	Write-Error "ClientId not provided. Provide -ClientId or set AZURE_CLIENT_ID environment variable."
	exit 2
}

$ClientSecret = Prompt-ForSecretIfNeeded -Value $ClientSecret

# DryRun mode: print resolved values and exit before performing any network or install actions
if ($DryRun) {
	Write-Host "DryRun: resolved values (sensitive values masked)"
	$mask = { param($s) if ([string]::IsNullOrEmpty($s)) { return '<empty>' } elseif ($s.Length -le 8) { return ('*' * $s.Length) } else { return ($s.Substring(0,3) + ('*' * ([Math]::Max(0,$s.Length-6))) + $s.Substring($s.Length-3)) } }
	Write-Host "TenantId: $($TenantId)"
	Write-Host "ClientId: $($ClientId)"
	Write-Host "ClientSecret: $(& $mask $ClientSecret)"
	Write-Host "AdminUrl: $($AdminUrl)"
	Write-Host "Search: $($Search)"
	Write-Host "ListLists: $($ListLists.IsPresent)"
	Write-Host "AutoInstallModule: $($AutoInstallModule.IsPresent)"
	exit 0
}

# Ensure PnP.PowerShell module is available
if (-not (Get-Module -ListAvailable -Name PnP.PowerShell)) {
	if ($AutoInstallModule) {
		Write-Host "Installing PnP.PowerShell module (CurrentUser)..."
		Install-Module PnP.PowerShell -Scope CurrentUser -Force -AllowClobber
	}
	else {
		Write-Host "PnP.PowerShell module is not installed. Run 'Install-Module PnP.PowerShell -Scope CurrentUser' or re-run with -AutoInstallModule to install automatically."
		exit 4
	}
}

Import-Module PnP.PowerShell -ErrorAction Stop

# If AdminUrl not provided, attempt to infer from Search if it looks like a site URL
if (-not $AdminUrl) {
	if ($Search -match 'https?://([^.]+)\.sharepoint\.com') {
		$tenant = $matches[1]
		$AdminUrl = "https://$($tenant)-admin.sharepoint.com"
		Write-Host "Inferred AdminUrl: $AdminUrl"
	}
}

if (-not $AdminUrl) {
	$AdminUrl = Read-Host -Prompt 'Enter tenant admin site URL (example: https://contoso-admin.sharepoint.com)'
	if (-not $AdminUrl) { Write-Error 'AdminUrl is required to enumerate tenant sites.'; exit 5 }
}

Write-Host "Connecting to tenant admin site: $AdminUrl"
try {
	Connect-PnPOnline -Url $AdminUrl -ClientId $ClientId -ClientSecret $ClientSecret -Tenant $TenantId -ErrorAction Stop
}
catch {
	Write-Error "Failed to connect to PnP with app credentials: $($_.Exception.Message)"
	exit 6
}

# Get tenant sites (requires tenant admin privileges). Filter client-side by Title or Url using $Search.
Write-Host "Retrieving tenant sites... (this may take a while for large tenants)"
try {
	$allSites = Get-PnPTenantSite -IncludeOneDriveSites:$false -Detailed -ErrorAction Stop
}
catch {
	Write-Error "Get-PnPTenantSite failed: $($_.Exception.Message)"
	exit 7
}

if ($Search -and $Search -ne '*') {
	$pattern = "*$Search*"
	$sites = $allSites | Where-Object { ($_.'Title' -and $_.Title -like $pattern) -or ($_.Url -and $_.Url -like $pattern) }
}
else { $sites = $allSites }

if (-not $sites -or $sites.Count -eq 0) {
	Write-Host "No sites matched the search criteria."
	exit 0
}

foreach ($site in $sites) {
	Write-Host "---"
	Write-Host "Site: $($site.Title)"
	Write-Host "Url:  $($site.Url)"
	if ($site.SiteId) { Write-Host "SiteId: $($site.SiteId)" }

	if ($ListLists) {
		Write-Host "  Fetching lists for site..."
		try {
			# Connect to the site and list lists
			$conn = Connect-PnPOnline -Url $site.Url -ClientId $ClientId -ClientSecret $ClientSecret -Tenant $TenantId -ReturnConnection -ErrorAction Stop
			$lists = Get-PnPList -Connection $conn -ErrorAction Stop
			if ($lists -and $lists.Count -gt 0) {
				foreach ($L in $lists) {
					Write-Host "    List: $($L.Title) (Id: $($L.Id))"
				}
			}
			else { Write-Host "    No lists found or no access." }
		}
		catch {
			Write-Host "    Failed to enumerate lists for site: $($_.Exception.Message)"
		}
	}
}

Write-Host "Done. Listed $($sites.Count) sites."
