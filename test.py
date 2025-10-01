import subprocess, json, sys
# run PowerShell script (adjust path if needed)
proc = subprocess.run(
    ["pwsh", "-File", "scripts/query_pnponline.ps1", "-EnvPath", ".env"],
    capture_output=True, text=True, check=False
)
# stdout will be JSON; stderr contains informational messages
if proc.returncode == 0:
    result = json.loads(proc.stdout)
    print("siteCount:", result.get("siteCount"))
else:
    err = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else {"error": proc.stderr}
    print("error:", err)