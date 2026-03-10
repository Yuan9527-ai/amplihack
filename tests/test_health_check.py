"""
Tests for src/amplihack/health_check.py

Coverage:
  Group A — HealthReport dataclass contracts (frozen, slots, tuple immutability)
  Group B — _check_dependency() paths (found / not-found / error)
  Group C — _check_path() paths (exists / absent / OSError / no leakage)
  Group D — check_health() integration (never raises, status classification)
  Group E — Status logic invariants (unhealthy > degraded, disjoint/union)
  Group F — _PROJECT_ROOT module constant (type, directory content)

41 tests total.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from amplihack.health_check import (
    _PROJECT_ROOT,
    HealthReport,
    _check_dependency,
    _check_path,
    check_health,
)

# ---------------------------------------------------------------------------
# Group A — HealthReport dataclass contracts (8 tests)
# ---------------------------------------------------------------------------


class TestHealthReportDataclass:
    """HealthReport is frozen, slot-limited, and uses tuples for check lists."""

    def test_frozen_prevents_attribute_assignment(self) -> None:
        """Cannot mutate a HealthReport after construction."""
        report = HealthReport(
            status="healthy",
            checks_passed=("dep:a",),
            checks_failed=(),
            details={},
        )
        with pytest.raises((AttributeError, TypeError)):
            report.status = "unhealthy"  # type: ignore[misc]

    def test_frozen_prevents_new_attribute(self) -> None:
        """Cannot add new attributes to a frozen dataclass."""
        report = HealthReport(
            status="healthy",
            checks_passed=(),
            checks_failed=(),
            details={},
        )
        with pytest.raises((AttributeError, TypeError)):
            report.new_field = "x"  # type: ignore[attr-defined]

    def test_slots_true_no_dict(self) -> None:
        """slots=True means instances have no __dict__."""
        report = HealthReport(
            status="healthy",
            checks_passed=(),
            checks_failed=(),
            details={},
        )
        assert not hasattr(report, "__dict__")

    def test_checks_passed_is_tuple(self) -> None:
        """checks_passed should be a tuple, not a list."""
        report = HealthReport(
            status="healthy",
            checks_passed=("dep:a",),
            checks_failed=(),
            details={},
        )
        assert isinstance(report.checks_passed, tuple)

    def test_checks_failed_is_tuple(self) -> None:
        """checks_failed should be a tuple, not a list."""
        report = HealthReport(
            status="unhealthy",
            checks_passed=(),
            checks_failed=("dep:b",),
            details={},
        )
        assert isinstance(report.checks_failed, tuple)

    def test_details_is_dict(self) -> None:
        """details field is a plain dict."""
        report = HealthReport(
            status="healthy",
            checks_passed=(),
            checks_failed=(),
            details={"dep:a": "found"},
        )
        assert isinstance(report.details, dict)

    def test_status_field_present(self) -> None:
        """status field is accessible and equals construction value."""
        report = HealthReport(
            status="degraded",
            checks_passed=("dep:a",),
            checks_failed=("path:x",),
            details={},
        )
        assert report.status == "degraded"

    def test_empty_report_is_valid(self) -> None:
        """HealthReport with all empty collections is constructable."""
        report = HealthReport(
            status="healthy",
            checks_passed=(),
            checks_failed=(),
            details={},
        )
        assert report.status == "healthy"
        assert report.checks_passed == ()
        assert report.checks_failed == ()


# ---------------------------------------------------------------------------
# Group B — _check_dependency() (7 tests)
# ---------------------------------------------------------------------------


class TestCheckDependency:
    """_check_dependency probes importability without executing package code."""

    def test_found_known_present_package(self) -> None:
        """A package that is genuinely importable returns (True, 'found')."""
        ok, msg = _check_dependency("sys")
        assert ok is True
        assert msg == "found"

    def test_not_found_missing_package(self) -> None:
        """A package that cannot be found returns (False, 'not found')."""
        ok, msg = _check_dependency("__amplihack_nonexistent_xyz__")
        assert ok is False
        assert msg == "not found"

    def test_not_found_message_string(self) -> None:
        """The 'not found' case returns exactly the string 'not found'."""
        _, msg = _check_dependency("__amplihack_nonexistent_xyz__")
        assert msg == "not found"

    def test_find_spec_returns_none(self) -> None:
        """When find_spec returns None the check reports not-found."""
        with patch("importlib.util.find_spec", return_value=None):
            ok, msg = _check_dependency("some_pkg")
        assert ok is False
        assert msg == "not found"

    def test_module_not_found_error_caught(self) -> None:
        """ModuleNotFoundError from find_spec is caught and returns (False, 'not found')."""
        with patch("importlib.util.find_spec", side_effect=ModuleNotFoundError):
            ok, msg = _check_dependency("some_pkg")
        assert ok is False
        assert msg == "not found"

    def test_value_error_caught(self) -> None:
        """ValueError from find_spec is caught and returns (False, 'not found')."""
        with patch("importlib.util.find_spec", side_effect=ValueError):
            ok, msg = _check_dependency("some_pkg")
        assert ok is False
        assert msg == "not found"

    def test_unexpected_exception_returns_internal_error(self) -> None:
        """An unexpected exception from find_spec returns (False, 'internal error')."""
        with patch("importlib.util.find_spec", side_effect=RuntimeError("boom")):
            ok, msg = _check_dependency("some_pkg")
        assert ok is False
        assert msg == "internal error"


# ---------------------------------------------------------------------------
# Group C — _check_path() (8 tests)
# ---------------------------------------------------------------------------


class TestCheckPath:
    """_check_path tests filesystem path existence and error handling."""

    def test_existing_path_returns_ok(self, tmp_path: Path) -> None:
        """An existing directory returns (True, 'ok')."""
        ok, msg = _check_path(str(tmp_path.name))
        # We patch _PROJECT_ROOT so we get a controlled environment
        with patch("amplihack.health_check._PROJECT_ROOT", tmp_path.parent):
            ok, msg = _check_path(tmp_path.name)
        assert ok is True
        assert msg == "ok"

    def test_missing_path_returns_not_found(self, tmp_path: Path) -> None:
        """A non-existent path returns (False, 'not found')."""
        with patch("amplihack.health_check._PROJECT_ROOT", tmp_path):
            ok, msg = _check_path("__does_not_exist__")
        assert ok is False
        assert msg == "not found"

    def test_existing_file_returns_ok(self, tmp_path: Path) -> None:
        """An existing file (not only dirs) returns (True, 'ok')."""
        f = tmp_path / "sample.txt"
        f.write_text("x")
        with patch("amplihack.health_check._PROJECT_ROOT", tmp_path):
            ok, msg = _check_path("sample.txt")
        assert ok is True
        assert msg == "ok"

    def test_os_error_caught(self) -> None:
        """OSError from path.exists() is caught; returns (False, 'internal error')."""
        with patch("pathlib.Path.exists", side_effect=OSError("permission denied")):
            ok, msg = _check_path("anything")
        assert ok is False
        assert msg == "internal error"

    def test_no_full_path_in_message(self, tmp_path: Path) -> None:
        """The returned message must not contain any filesystem paths."""
        with patch("amplihack.health_check._PROJECT_ROOT", tmp_path):
            _, msg = _check_path("__does_not_exist__")
        assert "/" not in msg
        assert "\\" not in msg

    def test_ok_message_is_exactly_ok(self, tmp_path: Path) -> None:
        """The success message is exactly the string 'ok'."""
        with patch("amplihack.health_check._PROJECT_ROOT", tmp_path):
            ok, msg = _check_path(str(tmp_path.name))  # checking tmp_path itself
        # tmp_path exists but is relative name — test with parent
        (tmp_path / "sub").mkdir()
        with patch("amplihack.health_check._PROJECT_ROOT", tmp_path):
            ok2, msg2 = _check_path("sub")
        assert msg2 == "ok"

    def test_not_found_message_exact(self, tmp_path: Path) -> None:
        """The not-found message is exactly 'not found'."""
        with patch("amplihack.health_check._PROJECT_ROOT", tmp_path):
            _, msg = _check_path("__nonexistent__")
        assert msg == "not found"

    def test_return_type_is_tuple_of_bool_and_str(self, tmp_path: Path) -> None:
        """Return value is a 2-tuple (bool, str)."""
        with patch("amplihack.health_check._PROJECT_ROOT", tmp_path):
            result = _check_path("__nonexistent__")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)


# ---------------------------------------------------------------------------
# Group D — check_health() integration (10 tests)
# ---------------------------------------------------------------------------


class TestCheckHealth:
    """check_health() must never raise and must classify status correctly."""

    def test_never_raises(self) -> None:
        """check_health() must not raise under any circumstances."""
        report = check_health()  # should not raise
        assert report is not None

    def test_returns_health_report_instance(self) -> None:
        """Return value is a HealthReport."""
        report = check_health()
        assert isinstance(report, HealthReport)

    def test_status_is_valid_value(self) -> None:
        """status is one of the three allowed values."""
        report = check_health()
        assert report.status in {"healthy", "degraded", "unhealthy"}

    def test_checks_passed_is_tuple(self) -> None:
        """checks_passed field is a tuple."""
        report = check_health()
        assert isinstance(report.checks_passed, tuple)

    def test_checks_failed_is_tuple(self) -> None:
        """checks_failed field is a tuple."""
        report = check_health()
        assert isinstance(report.checks_failed, tuple)

    def test_details_is_dict(self) -> None:
        """details field is a dict."""
        report = check_health()
        assert isinstance(report.details, dict)

    def test_all_deps_present_all_paths_present_is_healthy(self, tmp_path: Path) -> None:
        """When all deps found and all paths present, status is 'healthy'."""
        with (
            patch("amplihack.health_check._CRITICAL_DEPS", ("sys",)),
            patch("amplihack.health_check._CRITICAL_PATHS", (".")),
            patch("amplihack.health_check._PROJECT_ROOT", tmp_path),
        ):
            report = check_health()
        assert report.status == "healthy"

    def test_missing_dep_makes_unhealthy(self) -> None:
        """When a dep is missing, status must be 'unhealthy'."""
        with patch(
            "amplihack.health_check._CRITICAL_DEPS",
            ("__amplihack_nonexistent_xyz__",),
        ):
            report = check_health()
        assert report.status == "unhealthy"

    def test_all_deps_present_missing_path_is_degraded(self, tmp_path: Path) -> None:
        """When deps pass but a path is missing, status is 'degraded'."""
        with (
            patch("amplihack.health_check._CRITICAL_DEPS", ("sys",)),
            patch("amplihack.health_check._CRITICAL_PATHS", ("__nonexistent_path__",)),
            patch("amplihack.health_check._PROJECT_ROOT", tmp_path),
        ):
            report = check_health()
        assert report.status == "degraded"

    def test_does_not_raise_on_exception_inside(self) -> None:
        """Even when internal helpers raise, check_health() must not propagate."""
        with patch(
            "amplihack.health_check._check_dependency",
            side_effect=RuntimeError("unexpected"),
        ):
            try:
                check_health()
            except RuntimeError:
                pytest.fail("check_health() raised RuntimeError unexpectedly")


# ---------------------------------------------------------------------------
# Group E — Status logic invariants (6 tests)
# ---------------------------------------------------------------------------


class TestStatusLogicInvariants:
    """Verify the priority rules: unhealthy > degraded > healthy."""

    def test_unhealthy_beats_degraded(self) -> None:
        """If a dep fails, status is 'unhealthy' even with missing paths."""
        with (
            patch(
                "amplihack.health_check._CRITICAL_DEPS",
                ("__amplihack_nonexistent_xyz__",),
            ),
            patch(
                "amplihack.health_check._CRITICAL_PATHS",
                ("__also_missing__",),
            ),
        ):
            report = check_health()
        assert report.status == "unhealthy"

    def test_healthy_requires_no_failures(self, tmp_path: Path) -> None:
        """'healthy' only if checks_failed is empty."""
        with (
            patch("amplihack.health_check._CRITICAL_DEPS", ("sys",)),
            patch("amplihack.health_check._CRITICAL_PATHS", (".")),
            patch("amplihack.health_check._PROJECT_ROOT", tmp_path),
        ):
            report = check_health()
        assert report.checks_failed == ()

    def test_checks_passed_and_failed_are_disjoint(self) -> None:
        """No check name appears in both passed and failed."""
        report = check_health()
        assert set(report.checks_passed).isdisjoint(set(report.checks_failed))

    def test_union_of_passed_and_failed_equals_all_checks(self) -> None:
        """Every check key in details appears in either passed or failed."""
        report = check_health()
        all_checked = set(report.details.keys())
        all_classified = set(report.checks_passed) | set(report.checks_failed)
        assert all_checked == all_classified

    def test_degraded_has_nonempty_failed(self) -> None:
        """If status is 'degraded', checks_failed must be non-empty."""
        report = check_health()
        if report.status == "degraded":
            assert len(report.checks_failed) > 0

    def test_healthy_means_all_details_values_are_ok_or_found(self, tmp_path: Path) -> None:
        """In a 'healthy' run, every details value should be 'found' or 'ok'."""
        with (
            patch("amplihack.health_check._CRITICAL_DEPS", ("sys",)),
            patch("amplihack.health_check._CRITICAL_PATHS", (".")),
            patch("amplihack.health_check._PROJECT_ROOT", tmp_path),
        ):
            report = check_health()
        if report.status == "healthy":
            for val in report.details.values():
                assert val in {"found", "ok"}, f"Unexpected details value: {val!r}"


# ---------------------------------------------------------------------------
# Group F — _PROJECT_ROOT constant (2 tests)
# ---------------------------------------------------------------------------


class TestProjectRootConstant:
    """_PROJECT_ROOT is a module-level Path pointing at the project root."""

    def test_project_root_is_path(self) -> None:
        """_PROJECT_ROOT must be a pathlib.Path instance."""
        assert isinstance(_PROJECT_ROOT, Path)

    def test_project_root_is_a_directory(self) -> None:
        """_PROJECT_ROOT must point to an existing directory."""
        assert _PROJECT_ROOT.is_dir(), (
            f"_PROJECT_ROOT {_PROJECT_ROOT!r} is not an existing directory"
        )
