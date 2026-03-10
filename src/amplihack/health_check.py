"""
health_check — Environment diagnostic for the amplihack project.

Structural assumptions:
  - This file lives at src/amplihack/health_check.py
  - Project root is three .parent() calls from __file__
  - Critical paths are evaluated relative to project root

Public API:
  check_health() -> HealthReport
    Never raises. Returns status in {"healthy", "degraded", "unhealthy"}.

Status classification:
  healthy   — all critical deps found AND all critical paths exist
  degraded  — all critical deps found BUT ≥1 critical path missing
  unhealthy — ≥1 critical dep missing (paths not checked)
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

# Module-level constant — computed once at import time
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent

_CRITICAL_DEPS: tuple[str, ...] = ("anthropic", "click", "rich")
_CRITICAL_PATHS: tuple[str, ...] = ("src", "tests", "pyproject.toml")


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Immutable snapshot of environment health."""

    status: str
    checks_passed: tuple[str, ...]
    checks_failed: tuple[str, ...]
    details: dict[str, str]


def check_health() -> HealthReport:
    """Run all health checks. Never raises.

    Returns:
        HealthReport with status in {"healthy", "degraded", "unhealthy"}.

    Example:
        >>> report = check_health()
        >>> report.status in {"healthy", "degraded", "unhealthy"}
        True
    """
    try:
        return _run_checks()
    except Exception:
        return HealthReport(
            status="unhealthy",
            checks_passed=(),
            checks_failed=("internal error",),
            details={"internal error": "unexpected failure in health check"},
        )


def _run_checks() -> HealthReport:
    """Execute all checks and return a HealthReport. May raise only internally."""
    checks_passed: list[str] = []
    checks_failed: list[str] = []
    details: dict[str, str] = {}

    dep_failed = False
    for dep in _CRITICAL_DEPS:
        ok, msg = _check_dependency(dep)
        details[dep] = msg
        if ok:
            checks_passed.append(dep)
        else:
            checks_failed.append(dep)
            dep_failed = True

    if not dep_failed:
        for path_name in _CRITICAL_PATHS:
            ok, msg = _check_path(path_name)
            details[path_name] = msg
            if ok:
                checks_passed.append(path_name)
            else:
                checks_failed.append(path_name)

    if dep_failed:
        status = "unhealthy"
    elif checks_failed:
        status = "degraded"
    else:
        status = "healthy"

    return HealthReport(
        status=status,
        checks_passed=tuple(checks_passed),
        checks_failed=tuple(checks_failed),
        details=details,
    )


def _check_dependency(name: str) -> tuple[bool, str]:
    """Check if a package is importable without executing it.

    Args:
        name: Package name to check.

    Returns:
        (True, "found") if importable, (False, "not found") if absent,
        (False, "internal error") if find_spec raises.
    """
    try:
        found = importlib.util.find_spec(name) is not None
        return found, "found" if found else "not found"
    except (ModuleNotFoundError, ValueError):
        return False, "not found"
    except Exception:
        return False, "internal error"


def _check_path(name: str) -> tuple[bool, str]:
    """Check if a critical path exists. Returns basename only — no full paths.

    Args:
        name: Basename of the path to check relative to project root.

    Returns:
        (True, "ok") if path exists, (False, "not found") if absent,
        (False, "internal error") if filesystem raises.
    """
    try:
        exists = (_PROJECT_ROOT / name).exists()
        return exists, "ok" if exists else "not found"
    except OSError:
        return False, "internal error"
