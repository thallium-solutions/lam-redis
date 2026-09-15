#!/usr/bin/env python3
# Copyright 2026 Thallium Solutions di Busconi Alessandro.
# SPDX-License-Identifier: Apache-2.0
"""Compile @lam/redis tests exactly as an external scoped-package consumer."""

from __future__ import annotations

import argparse
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


LIB_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = LIB_ROOT / "tests"
COMPILER = os.environ.get("LAMC", "lamc")
MIN_COMPILER_VERSION = (1, 16, 0)
PACKAGE_PATH = Path("@lam") / "redis"
AUTH_REDIS_HOST = "127.0.0.1"
AUTH_REDIS_PORT = 6379


@dataclass(frozen=True)
class CaseResult:
    ok: bool
    phase: str
    detail: str = ""


def _compiler_version() -> tuple[int, int, int] | None:
    try:
        proc = subprocess.run(
            [COMPILER, "version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except FileNotFoundError:
        print(f"Error: {COMPILER!r} is not installed or is not on PATH.", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print(f"Error: {COMPILER!r} version check timed out.", file=sys.stderr)
        return None

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        print(f"Error: unable to check {COMPILER!r} version: {detail}", file=sys.stderr)
        return None

    text = proc.stdout.strip()
    match = re.fullmatch(r"(?:lamc\s+)?(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?", text)
    if match is None:
        print(f"Error: invalid {COMPILER!r} version output: {text!r}.", file=sys.stderr)
        return None

    version = tuple(int(part) for part in match.groups())
    if version < MIN_COMPILER_VERSION:
        required = ".".join(str(part) for part in MIN_COMPILER_VERSION)
        print(
            f"Error: {COMPILER} {text} is incompatible; lamc >= {required} is required.",
            file=sys.stderr,
        )
        return None
    return version


def _expectations(path: Path) -> list[str]:
    expected: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*#\s*expect:\s*(.*)$", line)
        if match:
            expected.append(match.group(1).strip())
    return expected


def _wait_for_service(host: str, port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _format_process_failure(label: str, proc: subprocess.CompletedProcess[str]) -> str:
    parts = [f"{label} exited with status {proc.returncode}"]
    if proc.stdout.strip():
        parts.append("stdout:\n" + proc.stdout.rstrip())
    if proc.stderr.strip():
        parts.append("stderr:\n" + proc.stderr.rstrip())
    return "\n".join(parts)


def _run_case(path: Path, *, compile_only: bool, race: bool) -> CaseResult:
    expected = _expectations(path)
    try:
        with tempfile.TemporaryDirectory(prefix="lamredis_consumer_") as tmp:
            consumer_root = Path(tmp)
            extlibs = consumer_root / "extlibs"
            package = extlibs / PACKAGE_PATH
            package.parent.mkdir(parents=True)
            package.symlink_to(LIB_ROOT, target_is_directory=True)
            binary = consumer_root / "test_binary"
            command = [
                COMPILER,
                str(path),
                "--extlibs",
                str(extlibs),
                "--no-cache",
                "-o",
                str(binary),
            ]
            if race:
                command.append("--go-race")

            compile_proc = subprocess.run(
                command,
                cwd=consumer_root,
                capture_output=True,
                text=True,
                timeout=240,
                check=False,
            )
            if compile_proc.returncode != 0:
                return CaseResult(False, "compile", _format_process_failure("lamc", compile_proc))
            if compile_only:
                return CaseResult(True, "compile")

            run_proc = subprocess.run(
                [str(binary)],
                cwd=consumer_root,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                env=os.environ.copy(),
            )
            if run_proc.returncode != 0:
                return CaseResult(False, "run", _format_process_failure("test binary", run_proc))

            actual = run_proc.stdout.rstrip("\n")
            expected_text = "\n".join(expected).strip()
            if expected and actual != expected_text:
                return CaseResult(
                    False,
                    "output",
                    f"expected:\n{expected_text}\n\nactual:\n{actual}",
                )
            return CaseResult(True, "run")
    except subprocess.TimeoutExpired as exc:
        return CaseResult(False, exc.cmd[0] if exc.cmd else "process", f"timed out after {exc.timeout}s")
    except OSError as exc:
        return CaseResult(False, "setup", str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(description="@lam/redis consumer integration tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="show complete failure details")
    parser.add_argument("--race", action="store_true", help="compile with Go's race detector")
    parser.add_argument(
        "--compile-only",
        action="store_true",
        help="verify package resolution and compilation without contacting Redis",
    )
    parser.add_argument(
        "--service-timeout",
        type=float,
        default=10.0,
        help="seconds to wait for localhost:6379 before running tests (default: 10)",
    )
    args = parser.parse_args()

    version = _compiler_version()
    if version is None:
        return 1

    cases = sorted(TEST_ROOT.glob("test_stdlib_lamredis*.lam"))
    if not cases:
        print("Error: no Redis test cases found.", file=sys.stderr)
        return 1

    if not args.compile_only and not _wait_for_service(AUTH_REDIS_HOST, AUTH_REDIS_PORT, args.service_timeout):
        print(
            "Error: authenticated Redis is unavailable at 127.0.0.1:6379.\n"
            "Start it with `lamc lib run service` (or `sh test-services.sh`) in another terminal,\n"
            "then rerun the tests. Use --compile-only when Docker is unavailable.",
            file=sys.stderr,
        )
        return 1

    mode = "compile" if args.compile_only else "integration"
    print(f"Using {COMPILER} {'.'.join(str(part) for part in version)}")
    print(f"Running {len(cases)} @lam/redis {mode} test(s)...\n")

    failures: list[tuple[Path, CaseResult]] = []
    for case in cases:
        result = _run_case(case, compile_only=args.compile_only, race=args.race)
        relative = case.relative_to(LIB_ROOT)
        print(f"  {'PASS' if result.ok else 'FAIL'}  {relative} ({result.phase})")
        if not result.ok:
            failures.append((relative, result))
            if args.verbose:
                for line in result.detail.splitlines():
                    print(f"        {line}")

    passed = len(cases) - len(failures)
    print(f"\n@lam/redis results: {passed} passed, {len(failures)} failed, {len(cases)} total")
    if failures and not args.verbose:
        print("Rerun with --verbose for complete diagnostics.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
