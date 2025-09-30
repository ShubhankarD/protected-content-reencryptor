"""
Authentication module using Microsoft Identity (MSAL).
Handles login flow for multiple Microsoft accounts.
"""
import json
import os
from typing import List, Optional
import msal
import logging
from logging_setup import configure_file_logging
from dotenv import load_dotenv


load_dotenv()


class AuthManager:
    """Manage authentication for both public (interactive) and confidential (client credentials) flows.

    Behavior:
    - If CLIENT_SECRET (in env or config) is present, uses ConfidentialClientApplication and
      the client credentials flow (app-only tokens).
    - Otherwise, uses PublicClientApplication and supports interactive login and silent token
      acquisition for delegated flows.

    The manager will persist a MSAL SerializableTokenCache to `cache_path`.
    """

    def __init__(self, config: Optional[dict] = None, cache_path: str = "token_cache.bin"):
        # Load config from provided dict or from config.json if available
        if config is None:
            try:
                here = os.path.dirname(__file__)
                cfg_path = os.path.join(here, "..", "config.json")
                with open(os.path.abspath(cfg_path), "r", encoding="utf-8") as fh:
                    config = json.load(fh)
            except Exception:
                config = {}

        # Allow environment variables to override config.json values
        client_id = os.getenv("CLIENT_ID") or config.get("client_id")
        client_secret = os.getenv("CLIENT_SECRET") or config.get("client_secret")
        # If AUTHORITY isn't explicitly set, prefer building it from TENANT_ID if available
        tenant_id = os.getenv("TENANT_ID") or config.get("tenant_id")
        authority = os.getenv("AUTHORITY") or config.get("authority")
        if not authority:
            if tenant_id:
                authority = f"https://login.microsoftonline.com/{tenant_id}"
            else:
                authority = "https://login.microsoftonline.com/common"

        if not client_id:
            raise ValueError("CLIENT_ID must be set via environment or config.json")

        self.config = config
        self.cache_path = cache_path
        self.token_cache = msal.SerializableTokenCache()
        # Load token cache from file if exists (text mode)
        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    data = f.read()
                    if data:
                        self.token_cache.deserialize(data)
        except Exception:
            # non-fatal
            pass

        # Prefer confidential client if we have a client secret
        if client_secret:
            self.app = msal.ConfidentialClientApplication(
                client_id,
                client_credential=client_secret,
                authority=authority,
                token_cache=self.token_cache,
            )
            self.client_mode = "confidential"
        else:
            self.app = msal.PublicClientApplication(
                client_id,
                authority=authority,
                token_cache=self.token_cache,
            )
            self.client_mode = "public"

        self.access_token: Optional[str] = None

        # logger for diagnostics; respect LOG_LEVEL env var
        self.logger = logging.getLogger("AuthManager")
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        try:
            self.logger.setLevel(getattr(logging, log_level))
        except Exception:
            self.logger.setLevel(logging.INFO)
        # Configure reusable file logging; returns absolute path to log file
        try:
            # If user provided LOG_LEVEL use it; otherwise let helper default to DEBUG
            # Attach file logging specifically to the AuthManager and msal loggers so
            # their records are guaranteed to be written to the same file handler.
            # If user provided LOG_LEVEL use it; otherwise let helper default to DEBUG
            if os.getenv("LOG_LEVEL"):
                msal_log_path = configure_file_logging(logger_names=["AuthManager", "msal"], level=log_level)
            else:
                msal_log_path = configure_file_logging(logger_names=["AuthManager", "msal"])
        except Exception:
            msal_log_path = "logs/msal.log"

        # Ensure a stream handler exists for interactive console output (only add if missing)
        if not any(isinstance(h, logging.StreamHandler) for h in self.logger.handlers):
            ch = logging.StreamHandler()
            ch.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s"))
            self.logger.addHandler(ch)

    def _save_cache(self) -> None:
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                f.write(self.token_cache.serialize())
        except Exception:
            # non-fatal; continue
            pass

    def acquire_token_for_client(self, scopes: Optional[List[str]] = None) -> dict:
        """Acquire an app-only token using client credentials flow.

        Returns the raw MSAL result dict. Default scope is ['https://graph.microsoft.com/.default']
        which uses the application's assigned app roles/permissions.
        """
        if self.client_mode != "confidential":
            raise RuntimeError("Client credentials flow requires CLIENT_SECRET (confidential client)")

        if scopes is None:
            scopes = ["https://graph.microsoft.com/.default"]

        try:
            result = self.app.acquire_token_silent(scopes, account=None)
        except Exception as exc:
            self.logger.debug("acquire_token_silent raised: %s", exc)
            result = None

        if not result or "access_token" not in result:
            result = self.app.acquire_token_for_client(scopes=scopes)

        if not result or "access_token" not in result:
            # Log the full MSAL result dict for diagnostics at ERROR so it appears
            # in file logs even if DEBUG-level console logging is disabled.
            try:
                self.logger.error("acquire_token_for_client failed, MSAL result: %s", json.dumps(result, indent=2))
            except Exception:
                self.logger.error("acquire_token_for_client failed, MSAL result: %s", result)
        else:
            self.access_token = result["access_token"]
            self._save_cache()
        return result

    def acquire_token_interactive(self, scopes: Optional[List[str]] = None) -> dict:
        """Interactive login (delegated permissions). Works only for PublicClientApplication.

        Tries silent first, then interactive if needed.
        """
        if scopes is None:
            scopes = ["User.Read", "Files.ReadWrite.All"]

        if self.client_mode != "public":
            raise RuntimeError("Interactive flow requires a public client (no CLIENT_SECRET)")

        accounts = self.app.get_accounts()
        if accounts:
            try:
                result = self.app.acquire_token_silent(scopes, account=accounts[0])
            except Exception as exc:
                self.logger.debug("acquire_token_silent (interactive path) raised: %s", exc)
                result = None
            if result and "access_token" in result:
                self.access_token = result["access_token"]
                return result
            else:
                try:
                    self.logger.error("acquire_token_silent (interactive) returned: %s", json.dumps(result, indent=2))
                except Exception:
                    self.logger.error("acquire_token_silent (interactive) returned: %s", result)

        try:
            result = self.app.acquire_token_interactive(scopes=scopes)
        except Exception as exc:
            self.logger.debug("acquire_token_interactive raised: %s", exc)
            raise Exception(f"Interactive login failed (exception): {exc}")

        if result and "access_token" in result:
            self.access_token = result["access_token"]
            self._save_cache()
            return result
        # Log result for troubleshooting
        try:
            self.logger.error("acquire_token_interactive failed, MSAL result: %s", json.dumps(result, indent=2))
        except Exception:
            self.logger.error("acquire_token_interactive failed, MSAL result: %s", result)
        raise Exception(f"Interactive login failed: {result.get('error_description') if result else 'no result'}")

    def get_token(self, scopes: Optional[List[str]] = None, interactive: bool = False) -> Optional[str]:
        """High level helper to return an access token.

        - If in confidential mode, obtains an app-only token (scopes default to /.default)
        - If in public mode, tries silent and optionally interactive (when interactive=True)
        """
        if self.client_mode == "confidential":
            res = self.acquire_token_for_client(scopes)
            return res.get("access_token") if res else None

        # public client
        if scopes is None:
            scopes = ["User.Read"]

        accounts = self.app.get_accounts()
        if accounts:
            try:
                res = self.app.acquire_token_silent(scopes, account=accounts[0])
            except Exception as exc:
                self.logger.debug("acquire_token_silent (get_token) raised: %s", exc)
                res = None
            if res and "access_token" in res:
                return res["access_token"]
            else:
                try:
                    self.logger.error("acquire_token_silent (get_token) returned: %s", json.dumps(res, indent=2))
                except Exception:
                    self.logger.error("acquire_token_silent (get_token) returned: %s", res)

        if interactive:
            res = self.acquire_token_interactive(scopes)
            return res.get("access_token") if res else None

        return None


if __name__ == "__main__":
    # Quick demo when run directly. Prints whether confidential or public and tries to acquire a token.
    am = AuthManager()
    print(f"Client mode: {am.client_mode}")
    try:
        token = am.get_token(interactive=(am.client_mode == "public"))
        print("Access token obtained:" , bool(token))
    except Exception as exc:
        print("Auth error:", exc)
