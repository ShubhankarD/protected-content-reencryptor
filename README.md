# Microsoft Graph API Demo Project

## Overview
This repository is a small demo that shows how to authenticate with Microsoft Identity (MSAL),
generate dummy files, (mock) apply sensitivity labels, and upload files to SharePoint/OneDrive.

## Structure
- `src/auth.py` – authentication helper (`AuthManager`) using MSAL
- `src/data_generation.py` – dummy file generation
- `src/labeling.py` – sensitivity label application (mock)
- `src/storage.py` – file upload helpers
- `config.json` / `.env` – configuration and secrets

## Authentication (AuthManager)
`AuthManager` in `src/auth.py` supports both:
- Confidential (app-only) flow via client credentials when `CLIENT_SECRET` is set.
- Public (delegated) interactive flow when `CLIENT_SECRET` is absent.

Configuration precedence
- Environment variables take precedence over `config.json` values. `AuthManager` calls `load_dotenv()` so a local `.env` file is supported.
- Key settings:
   - `CLIENT_ID` (required)
   - `CLIENT_SECRET` (optional; enables confidential client / client-credentials)
   - `TENANT_ID` or `AUTHORITY` (optional; if not provided, the code uses `common`)

Example `config.json` (template, do not commit secrets):
```json
{
   "client_id": "<YOUR_CLIENT_ID>",
   "tenant_id": "yourtenant.onmicrosoft.com",
   "authority": "https://login.microsoftonline.com/yourtenant.onmicrosoft.com"
}
```

Running the auth demo
1. Install deps: `pip install -r requirements.txt`
2. Provide credentials via `.env` or `config.json`.
3. Run the small demo:
```powershell
$env:LOG_LEVEL='DEBUG'
python src/auth.py
```
It prints the client mode (confidential or public) and whether an access token was obtained.

Debugging and logs
- `AuthManager` writes a file log under `logs/` (the helper `src/logging_setup.py` configures a rotating file handler).
- Set `LOG_LEVEL=DEBUG` to capture MSAL HTTP activity and the MSAL result dict (the script logs MSAL results at ERROR level so they appear in file logs).

Common MSAL errors and fixes
- `unauthorized_client` / AADSTS700016: Application with identifier '...'' was not found in the directory
   - Cause: `CLIENT_ID` does not exist in the tenant you are authenticating against (wrong tenant, single-tenant app used from other tenant, or missing consent).
   - Fixes: ensure `CLIENT_ID` matches the app registration in the tenant, or set `AUTHORITY`/`TENANT_ID` to the tenant that owns the app. For app-only flows, add Application permissions and grant admin consent.
- `invalid_scope`: using delegated scopes with client credentials or incorrect scope format
   - Fix: for client-credentials use `['https://graph.microsoft.com/.default']`. For delegated flows use permission names like `['User.Read']`.
- `invalid_client`: client secret missing or incorrect
   - Fix: ensure `CLIENT_SECRET` is set (if using confidential client) and matches the secret in App Registration → Certificates & secrets.

If you run into issues, enable `LOG_LEVEL=DEBUG`, rerun `src/auth.py`, then check the latest `logs/auth_*.log` file for the MSAL result dict and share it when asking for help.

Next steps
- Implement real Graph calls in `src/storage.py` and `src/labeling.py`.
- Replace `config.json` with a `config.example.json` and add `config.json` to `.gitignore` if you plan to keep local overrides.

---
Short, focused changes to `src/auth.py` and `src/logging_setup.py` were recently made to improve logging and help debug MSAL failures. See the file comments for details.
