"""Command-line entry point for CalendarDB authentication."""

from __future__ import annotations

import argparse
import sys

from calendardb.auth import CalendarAuthError, login, logout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="calendardb")
    commands = parser.add_subparsers(dest="command", required=True)

    login_parser = commands.add_parser("login", help="Authorize CalendarDB with Google")
    login_parser.add_argument("--client-secrets", required=True, metavar="PATH")
    commands.add_parser("logout", help="Remove saved CalendarDB authorization")
    args = parser.parse_args(argv)
    try:
        if args.command == "login":
            login(args.client_secrets)
            print("CalendarDB authorization saved in the system keychain.")
        elif args.command == "logout":
            logout()
            print("CalendarDB authorization removed from the system keychain.")
    except CalendarAuthError as error:
        print(f"calendardb: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
