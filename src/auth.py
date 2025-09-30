"""
Authentication module using Microsoft Identity (MSAL).
Handles login flow for multiple Microsoft accounts.
"""
import msal
import os
from dotenv import load_dotenv

import pickle

class AuthManager:
    def __init__(self, config, cache_path="token_cache.bin"):
        self.config = config
        self.cache_path = cache_path
        self.token_cache = msal.SerializableTokenCache()
        # Load token cache from file if exists
        try:
            with open(self.cache_path, "rb") as f:
                self.token_cache.deserialize(f.read())
        except FileNotFoundError:
            pass
        self.app = msal.PublicClientApplication(
            self.config.get("client_id"),
            authority=self.config.get("authority"),
            token_cache=self.token_cache
        )


    def login(self, scopes=["User.Read", "Files.ReadWrite.All"]):
        """
        Interactive browser login flow. Saves auth session to token cache for persistence.
        """
        accounts = self.app.get_accounts()
        if accounts:
            # Try to acquire token silently
            result = self.app.acquire_token_silent(scopes, account=accounts[0])
            if result and "access_token" in result:
                print(f"Silent login successful for {accounts[0]['username']}")
                self.access_token = result["access_token"]
                return
        # Interactive login
        result = self.app.acquire_token_interactive(scopes=scopes)
        if "access_token" in result:
            print("Interactive login successful.")
            self.access_token = result["access_token"]
            # Save token cache
            with open(self.cache_path, "wb") as f:
                f.write(self.token_cache.serialize())
        else:
            raise Exception(f"Login failed: {result.get('error_description')}")

    def get_token(self):
        """
        Retrieve access token after login.
        """
        return getattr(self, "access_token", None)
