from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import sys
from pathlib import Path
from typing import Any

from telegram_osint.config import ConfigError, load_config
from telegram_osint.daemon import run_daemon
from telegram_osint.ipc import ControlClient
from telegram_osint.session import OpenTele2Converter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tg-osint")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="account YAML configuration",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    commands = parser.add_subparsers(dest="command", required=True)

    daemon = commands.add_parser("daemon", help="run the foreground daemon")
    session = commands.add_parser("session", help="manage authenticated sessions")
    session_subcommands = session.add_subparsers(dest="session_command", required=True)
    import_tdata = session_subcommands.add_parser("import-tdata")
    import_tdata.add_argument("--tdata", type=Path, required=True)
    import_tdata.add_argument("--output", type=Path, required=True)
    import_tdata.add_argument("--force", action="store_true")

    commands.add_parser("status")
    commands.add_parser("chats")

    target = commands.add_parser("targets")
    target.add_argument("action", choices=("list", "add", "remove", "media"))
    target.add_argument("chat_id", type=int, nargs="?")
    target.add_argument(
        "--enabled",
        choices=("true", "false"),
        help="required for the media action",
    )

    user = commands.add_parser("user-scrape")
    user.add_argument("user_id", type=int)
    user.add_argument(
        "--photos",
        choices=("off", "current", "all_visible_history"),
        default="current",
    )

    job = commands.add_parser("job-show")
    job.add_argument("job_id")

    return parser


async def _request(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config(args.config)
    client = ControlClient(config.paths.socket)
    if args.command == "status":
        return await client.request("status", {})
    if args.command == "chats":
        return await client.request("chats.list", {})
    if args.command == "user-scrape":
        return await client.request(
            "users.scrape",
            {"user_id": args.user_id, "photos": args.photos},
        )
    if args.command == "targets":
        if args.action == "list":
            return await client.request("targets.list", {})
        if args.chat_id is None:
            raise ConfigError("targets add/remove/media requires CHAT_ID")
        arguments: dict[str, Any] = {
            "chat_id": args.chat_id,
            "expected_hash": config.config_hash,
        }
        if args.action == "media":
            if args.enabled is None:
                raise ConfigError("targets media requires --enabled true|false")
            arguments["enabled"] = args.enabled == "true"
        return await client.request(f"targets.{args.action}", arguments)
    if args.command == "job-show":
        return await client.request("jobs.show", {"job_id": args.job_id})
    raise RuntimeError(f"unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "daemon":
            run_daemon(args.config)
            return 0
        if args.command == "session":
            if args.session_command != "import-tdata":
                raise ConfigError("unsupported session command")
            passcode = getpass.getpass(
                "tdata passcode (leave empty if none): "
            ) or None
            result = OpenTele2Converter().convert(
                args.tdata,
                args.output,
                passcode=passcode,
                force=args.force,
            )
            print(json.dumps(result, sort_keys=True))
            return 0
        response = asyncio.run(_request(args))
    except (ConfigError, OSError, RuntimeError, ConnectionError) as error:
        parser.exit(2, f"error: {error}\n")
    if args.json:
        print(json.dumps(response, sort_keys=True))
    elif response.get("ok"):
        print(json.dumps(response["result"], indent=2, sort_keys=True))
    else:
        print(f"error: {response.get('error')}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
