from unittest.mock import patch

from calendardb import cli
from calendardb.auth import CalendarAuthError


def test_login_cli_never_displays_secret_material(capsys):
    with patch.object(cli, "login"):
        assert cli.main(["login", "--client-secrets", "/private/client.json"]) == 0
    output = capsys.readouterr().out
    assert output == "CalendarDB authorization saved in the system keychain.\n"
    assert "/private" not in output


def test_cli_auth_failure_is_safe(capsys):
    with patch.object(cli, "login", side_effect=CalendarAuthError("safe message")):
        assert cli.main(["login", "--client-secrets", "client.json"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "calendardb: safe message\n"


def test_logout_cli_reports_completion(capsys):
    with patch.object(cli, "logout"):
        assert cli.main(["logout"]) == 0
    assert capsys.readouterr().out == "CalendarDB authorization removed from the system keychain.\n"
