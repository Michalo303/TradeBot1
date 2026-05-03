"""Repository safety checks for TradeBot1.

The project is intentionally public, while runtime credentials and bot state
stay local/server-side. These checks guard the repo against the mistakes that
matter most for this setup.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_TRACKED_PATTERNS = (
    re.compile(r"(^|/)AGENTS\.md$"),
    re.compile(r"(^|/)user_data/config/config\.private\.json$"),
    re.compile(r"(^|/)user_data/data/"),
    re.compile(r"(^|/)user_data/logs/"),
    re.compile(r"(^|/)user_data/backtest_results/"),
    re.compile(r"\.sqlite(-shm|-wal)?$"),
    re.compile(r"(^|/)user_data/nfix7-.*\.json$"),
)

SECRET_REGEXES = (
    re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b"),
    re.compile(r'"password"\s*:\s*"(?!CHANGE_THIS_PASSWORD)[^"]{10,}"'),
    re.compile(r'"jwt_secret_key"\s*:\s*"(?!CHANGE_THIS_JWT_SECRET_32_CHARS_MIN)[A-Za-z0-9_-]{32,}"'),
    re.compile(r'"ws_token"\s*:\s*"(?!CHANGE_THIS_WS_TOKEN)[A-Za-z0-9_-]{16,}"'),
)

TEXT_FILE_SUFFIXES = {
    ".env",
    ".example",
    ".gitignore",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def git_ls_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def check_no_forbidden_tracked_files(tracked: list[str]) -> None:
    for path in tracked:
        for pattern in FORBIDDEN_TRACKED_PATTERNS:
            if pattern.search(path):
                fail(f"forbidden runtime/private file is tracked: {path}")


def check_no_known_secrets(tracked: list[str]) -> None:
    for path in tracked:
        full_path = ROOT / path
        if full_path.suffix not in TEXT_FILE_SUFFIXES and not path.endswith(".env.example"):
            continue
        if path == "user_data/strategies/NostalgiaForInfinityX7.py":
            continue
        try:
            content = full_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_REGEXES:
            if pattern.search(content):
                fail(f"possible private value leaked in tracked file: {path}")


def check_docker_web_ui_binding() -> None:
    compose = read("docker-compose.yml")
    if "127.0.0.1:8080:8080" not in compose:
        fail("Web UI must be bound to 127.0.0.1:8080:8080, not exposed publicly")
    if re.search(r'["\']8080:8080["\']', compose):
        fail("docker-compose.yml exposes Web UI publicly as 8080:8080")


def check_freqtrade_config() -> None:
    config = json.loads(read("user_data/config/config.json"))
    if config.get("dry_run") is not True:
        fail("config.json must keep dry_run=true in the public default config")
    if "add_config_files" in config:
        fail("blacklist config should be loaded only through docker-compose --config args")


def check_json_templates() -> None:
    for path in (
        "user_data/config/config.json",
        "user_data/config/config.private.json.example",
        "user_data/config/pairlist-backtest-local.json",
        "user_data/config/pairlist-backtest-static-binance-spot-usdt.json",
    ):
        json.loads(read(path))


def main() -> None:
    tracked = git_ls_files()
    check_no_forbidden_tracked_files(tracked)
    check_no_known_secrets(tracked)
    check_docker_web_ui_binding()
    check_freqtrade_config()
    check_json_templates()
    print("PASS: repository safety checks passed")


if __name__ == "__main__":
    main()
