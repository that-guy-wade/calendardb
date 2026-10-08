"""Google OAuth credentials for CalendarDB."""

from __future__ import annotations

import json
import os

import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SERVICE_NAME = "calendardb"
KEYRING_ACCOUNT = "oauth"
TOKEN_ENV = "CALENDARDB_TOKEN"
SCOPES = [
    "https://www.googleapis.com/auth/calendar.app.created",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
]


class CalendarAuthError(Exception):
    """Safe-to-display authentication error."""


def _store(credentials: Credentials) -> None:
    try:
        keyring.set_password(SERVICE_NAME, KEYRING_ACCOUNT, credentials.to_json())
    except Exception:
        raise CalendarAuthError(
            "Could not save CalendarDB authorization in the system keychain."
        ) from None


def login(client_secrets: str) -> None:
    """Run Google's installed-app consent flow and save credentials securely."""
    try:
        flow = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES)
        credentials = flow.run_local_server(
            host="localhost",
            port=0,
            authorization_prompt_message="",
            success_message="CalendarDB authorization complete. You can close this window.",
            prompt="consent",
        )
    except Exception:
        raise CalendarAuthError(
            "Google authorization failed. Check the client-secrets file and try again."
        ) from None
    if not credentials.refresh_token:
        raise CalendarAuthError(
            "Google did not grant a refresh token; authorize CalendarDB again with offline access."
        )
    _store(credentials)


def logout() -> None:
    """Remove CalendarDB's saved OAuth credentials from the system keychain."""
    try:
        keyring.delete_password(SERVICE_NAME, KEYRING_ACCOUNT)
    except keyring.errors.PasswordDeleteError:
        pass
    except Exception:
        raise CalendarAuthError(
            "Could not remove CalendarDB authorization from the system keychain."
        ) from None


def _cached_credentials() -> Credentials:
    try:
        serialized = keyring.get_password(SERVICE_NAME, KEYRING_ACCOUNT)
    except Exception:
        raise CalendarAuthError(
            "Could not read CalendarDB authorization from the system keychain."
        ) from None
    if not serialized:
        raise CalendarAuthError(
            "CalendarDB is not logged in. Run `calendardb login --client-secrets PATH`."
        )
    try:
        info = json.loads(serialized)
        if not isinstance(info, dict):
            raise ValueError
        return Credentials.from_authorized_user_info(info, SCOPES)
    except Exception:
        raise CalendarAuthError(
            "Saved CalendarDB authorization is invalid. Run `calendardb login --client-secrets PATH`."
        ) from None


def get_access_token() -> str:
    """Return a bearer token, refreshing and securely persisting OAuth as needed."""
    token = os.environ.get(TOKEN_ENV)
    if token:
        return token
    credentials = _cached_credentials()
    if credentials.expired or not credentials.token:
        if not credentials.refresh_token:
            raise CalendarAuthError(
                "Saved CalendarDB authorization expired. Run `calendardb login --client-secrets PATH`."
            )
        try:
            credentials.refresh(Request())
        except Exception:
            raise CalendarAuthError(
                "Could not refresh CalendarDB authorization. Run `calendardb login --client-secrets PATH`."
            ) from None
        _store(credentials)
    if not credentials.valid:
        raise CalendarAuthError(
            "Saved CalendarDB authorization is unusable. Run `calendardb login --client-secrets PATH`."
        )
    return credentials.token
