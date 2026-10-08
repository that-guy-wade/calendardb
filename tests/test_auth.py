import json
from unittest.mock import Mock, patch

import pytest

from calendardb import auth


def test_environment_token_bypasses_keyring():
    with (
        patch.dict("os.environ", {auth.TOKEN_ENV: "env-token"}),
        patch.object(auth.keyring, "get_password", side_effect=AssertionError("keyring accessed")),
    ):
        assert auth.get_access_token() == "env-token"


def test_calendar_scopes_and_keyring_identity_are_independent_of_gmaildb():
    assert auth.SCOPES == [
        "https://www.googleapis.com/auth/calendar.app.created",
        "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    ]
    assert auth.SERVICE_NAME == "calendardb"
    assert auth.KEYRING_ACCOUNT == "oauth"
    assert auth.TOKEN_ENV == "CALENDARDB_TOKEN"


def test_missing_cached_credentials_has_safe_error():
    with patch.object(auth.keyring, "get_password", return_value=None):
        with pytest.raises(auth.CalendarAuthError, match="not logged in"):
            auth.get_access_token()


def test_invalid_cached_credentials_has_safe_error():
    with patch.object(auth.keyring, "get_password", return_value="not-json"):
        with pytest.raises(auth.CalendarAuthError, match="is invalid"):
            auth.get_access_token()


def test_expired_credentials_refresh_and_persist():
    credentials = Mock(expired=True, refresh_token="refresh", token="new-token", valid=True)
    with (
        patch.object(auth.keyring, "get_password", return_value=json.dumps({"token": "old"})),
        patch.object(auth.Credentials, "from_authorized_user_info", return_value=credentials),
        patch.object(auth, "Request") as request,
        patch.object(auth, "_store") as store,
    ):
        assert auth.get_access_token() == "new-token"
    credentials.refresh.assert_called_once_with(request.return_value)
    store.assert_called_once_with(credentials)


def test_missing_access_token_refreshes_and_requires_valid_credentials():
    credentials = Mock(expired=False, refresh_token="refresh", token=None, valid=True)
    credentials.refresh.side_effect = lambda _request: setattr(credentials, "token", "new-token")
    with (
        patch.object(auth.keyring, "get_password", return_value=json.dumps({"token": None})),
        patch.object(auth.Credentials, "from_authorized_user_info", return_value=credentials),
        patch.object(auth, "Request"),
        patch.object(auth, "_store") as store,
    ):
        assert auth.get_access_token() == "new-token"
    credentials.refresh.assert_called_once()
    store.assert_called_once_with(credentials)


def test_login_requests_modify_scope_and_stores_refreshable_credentials():
    credentials = Mock(refresh_token="refresh")
    flow = Mock()
    flow.run_local_server.return_value = credentials
    with (
        patch.object(
            auth.InstalledAppFlow, "from_client_secrets_file", return_value=flow
        ) as create_flow,
        patch.object(auth, "_store") as store,
    ):
        auth.login("client.json")
    create_flow.assert_called_once_with(
        "client.json",
        [
            "https://www.googleapis.com/auth/calendar.app.created",
            "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
        ],
    )
    flow.run_local_server.assert_called_once_with(
        host="localhost",
        port=0,
        authorization_prompt_message="",
        success_message="CalendarDB authorization complete. You can close this window.",
        prompt="consent",
    )
    store.assert_called_once_with(credentials)


def test_login_rejects_non_persistent_credentials():
    flow = Mock()
    flow.run_local_server.return_value = Mock(refresh_token=None)
    with patch.object(auth.InstalledAppFlow, "from_client_secrets_file", return_value=flow):
        with pytest.raises(auth.CalendarAuthError, match="refresh token"):
            auth.login("client.json")


def test_logout_only_deletes_own_keyring_entry():
    with patch.object(auth.keyring, "delete_password") as delete:
        auth.logout()
    delete.assert_called_once_with(auth.SERVICE_NAME, auth.KEYRING_ACCOUNT)


def test_keyring_write_failure_has_no_plaintext_fallback():
    credentials = Mock(to_json=Mock(return_value='{"token":"secret-token"}'))
    with patch.object(auth.keyring, "set_password", side_effect=RuntimeError("secret-token")):
        with pytest.raises(auth.CalendarAuthError) as error:
            auth._store(credentials)
    assert "secret-token" not in str(error.value)


def test_refresh_failure_does_not_echo_secret_material():
    credentials = Mock(expired=True, refresh_token="refresh", token="old", valid=False)
    credentials.refresh.side_effect = RuntimeError("secret-token")
    with (
        patch.object(auth.keyring, "get_password", return_value=json.dumps({"token": "old"})),
        patch.object(auth.Credentials, "from_authorized_user_info", return_value=credentials),
        patch.object(auth, "Request"),
    ):
        with pytest.raises(auth.CalendarAuthError) as error:
            auth.get_access_token()
    assert "secret-token" not in str(error.value)
