"""Tests for backend capability detection module."""

import logging
import os
from unittest.mock import Mock, patch

import pytest

from pdf2foundry.backend.caps import (
    BackendCapabilities,
    detect_backend_capabilities,
    log_worker_resolution,
    resolve_effective_workers,
)


class TestBackendCapabilities:
    """Test BackendCapabilities dataclass."""

    def test_default_values(self) -> None:
        """Test default values."""
        caps = BackendCapabilities(supports_parallel_extract=True)

        assert caps.supports_parallel_extract is True
        assert caps.max_workers is None
        assert caps.start_method is None
        assert caps.platform is None
        assert caps.docling_version is None
        assert caps.notes is None

    def test_with_all_values(self) -> None:
        """Test with all values specified."""
        caps = BackendCapabilities(
            supports_parallel_extract=True,
            max_workers=4,
            start_method="fork",
            platform="linux",
            docling_version="1.0.0",
            notes=["test note"],
        )

        assert caps.supports_parallel_extract is True
        assert caps.max_workers == 4
        assert caps.start_method == "fork"
        assert caps.platform == "linux"
        assert caps.docling_version == "1.0.0"
        assert caps.notes == ["test note"]


class TestDetectBackendCapabilities:
    """Test detect_backend_capabilities function."""

    @patch("pdf2foundry.backend.caps.probe_docling")
    @patch("pdf2foundry.backend.caps.multiprocessing.get_start_method")
    @patch("pdf2foundry.backend.caps.os.cpu_count")
    def test_linux_fork_supported(self, mock_cpu_count: Mock, mock_get_start_method: Mock, mock_probe: Mock) -> None:
        """Test Linux with fork support enables parallel processing."""
        # Setup mocks
        mock_cpu_count.return_value = 8
        mock_get_start_method.return_value = "fork"
        mock_probe.return_value = Mock(
            has_docling=True,
            can_construct_converter=True,
            docling_version="1.0.0",
        )

        caps = detect_backend_capabilities(platform="linux")

        assert caps.supports_parallel_extract is True
        assert caps.max_workers == 8
        assert caps.start_method == "fork"
        assert caps.platform == "linux"
        assert caps.docling_version == "1.0.0"

    @patch("pdf2foundry.backend.caps.probe_docling")
    @patch("pdf2foundry.backend.caps.multiprocessing.get_start_method")
    def test_windows_spawn_unsupported(self, mock_get_start_method: Mock, mock_probe: Mock) -> None:
        """Test Windows with spawn method disables parallel processing."""
        mock_get_start_method.return_value = "spawn"
        mock_probe.return_value = Mock(
            has_docling=True,
            can_construct_converter=True,
            docling_version="1.0.0",
        )

        caps = detect_backend_capabilities(platform="win32")

        assert caps.supports_parallel_extract is False
        assert caps.start_method == "spawn"
        assert caps.platform == "win32"
        assert "Multiprocessing not safe on platform win32" in " ".join(caps.notes or [])

    @patch("pdf2foundry.backend.caps.probe_docling")
    def test_no_docling_unsupported(self, mock_probe: Mock) -> None:
        """Test missing Docling disables parallel processing."""
        mock_probe.return_value = Mock(
            has_docling=False,
            can_construct_converter=False,
            docling_version=None,
        )

        caps = detect_backend_capabilities()

        assert caps.supports_parallel_extract is False
        assert caps.docling_version is None
        assert "Docling version not available" in " ".join(caps.notes or [])

    @patch.dict(os.environ, {"PDF2FOUNDRY_SAFE_FORK": "true"})
    @patch("pdf2foundry.backend.caps.probe_docling")
    @patch("pdf2foundry.backend.caps.multiprocessing.get_start_method")
    @patch("pdf2foundry.backend.caps.os.cpu_count")
    def test_environment_override(self, mock_cpu_count: Mock, mock_get_start_method: Mock, mock_probe: Mock) -> None:
        """Test environment variable override for fork safety."""
        mock_cpu_count.return_value = 4
        mock_get_start_method.return_value = "spawn"
        mock_probe.return_value = Mock(
            has_docling=True,
            can_construct_converter=True,
            docling_version="1.0.0",
        )

        caps = detect_backend_capabilities(platform="win32")

        assert caps.supports_parallel_extract is True
        assert "Multiprocessing safety overridden by environment: True" in " ".join(caps.notes or [])

    @patch("pdf2foundry.backend.caps.probe_docling")
    @patch("pdf2foundry.backend.caps.multiprocessing.get_start_method")
    @patch("pdf2foundry.backend.caps.os.cpu_count")
    def test_cpu_count_fallback(self, mock_cpu_count: Mock, mock_get_start_method: Mock, mock_probe: Mock) -> None:
        """Test fallback when CPU count cannot be determined."""
        mock_cpu_count.side_effect = OSError("Cannot determine CPU count")
        mock_get_start_method.return_value = "fork"
        mock_probe.return_value = Mock(
            has_docling=True,
            can_construct_converter=True,
            docling_version="1.0.0",
        )

        caps = detect_backend_capabilities(platform="linux")

        assert caps.supports_parallel_extract is True
        assert caps.max_workers == 1
        assert "Could not determine CPU count" in " ".join(caps.notes or [])

    @patch("pdf2foundry.backend.caps.probe_docling")
    @patch("pdf2foundry.backend.caps.multiprocessing.get_start_method")
    @patch("pdf2foundry.backend.caps.os.cpu_count")
    def test_max_workers_capped(self, mock_cpu_count: Mock, mock_get_start_method: Mock, mock_probe: Mock) -> None:
        """Test max workers is capped at 8."""
        mock_cpu_count.return_value = 16
        mock_get_start_method.return_value = "fork"
        mock_probe.return_value = Mock(
            has_docling=True,
            can_construct_converter=True,
            docling_version="1.0.0",
        )

        caps = detect_backend_capabilities(platform="linux")

        assert caps.supports_parallel_extract is True
        assert caps.max_workers == 8  # Capped at 8

    def test_explicit_parameters(self) -> None:
        """Test with all parameters explicitly provided."""
        caps = detect_backend_capabilities(
            docling_version="1.0.0",
            platform="linux",
            safe_fork=True,
        )

        assert caps.supports_parallel_extract is True
        assert caps.platform == "linux"
        assert caps.docling_version == "1.0.0"


class TestResolveEffectiveWorkers:
    """Test resolve_effective_workers function."""

    def test_single_worker_requested(self) -> None:
        """Test single worker requested returns 1 with no reasons."""
        caps = BackendCapabilities(supports_parallel_extract=True, max_workers=4)

        effective, reasons = resolve_effective_workers(1, caps)

        assert effective == 1
        assert reasons == []

    def test_zero_workers_requested(self) -> None:
        """Test zero workers requested returns 1 with no reasons."""
        caps = BackendCapabilities(supports_parallel_extract=True, max_workers=4)

        effective, reasons = resolve_effective_workers(0, caps)

        assert effective == 1
        assert reasons == []

    def test_parallel_not_supported(self) -> None:
        """Test parallel processing not supported forces 1 worker."""
        caps = BackendCapabilities(supports_parallel_extract=False)

        effective, reasons = resolve_effective_workers(4, caps)

        assert effective == 1
        assert len(reasons) == 1
        assert "does not support parallel page extraction" in reasons[0]

    def test_backend_max_workers_clamp(self) -> None:
        """Test clamping to backend maximum workers."""
        caps = BackendCapabilities(supports_parallel_extract=True, max_workers=2)

        effective, reasons = resolve_effective_workers(4, caps)

        assert effective == 2
        assert len(reasons) == 1
        assert "Clamped to backend maximum of 2 workers" in reasons[0]

    def test_page_count_clamp(self) -> None:
        """Test clamping to page count."""
        caps = BackendCapabilities(supports_parallel_extract=True, max_workers=8)

        effective, reasons = resolve_effective_workers(4, caps, total_pages=2)

        assert effective == 2
        assert len(reasons) == 1
        assert "Clamped to page count of 2" in reasons[0]

    def test_multiple_clamps(self) -> None:
        """Test multiple clamping conditions."""
        caps = BackendCapabilities(supports_parallel_extract=True, max_workers=3)

        effective, reasons = resolve_effective_workers(8, caps, total_pages=2)

        assert effective == 2  # Final result after both clamps
        assert len(reasons) == 2
        assert "Clamped to backend maximum of 3 workers" in reasons[0]
        assert "Clamped to page count of 2" in reasons[1]

    def test_no_constraints(self) -> None:
        """Test no constraints returns requested workers."""
        caps = BackendCapabilities(supports_parallel_extract=True, max_workers=8)

        effective, reasons = resolve_effective_workers(4, caps, total_pages=10)

        assert effective == 4
        assert reasons == []

    def test_negative_effective_workers_forced_to_one(self) -> None:
        """Test negative effective workers is forced to 1."""
        # This is a theoretical edge case, but we should handle it
        caps = BackendCapabilities(supports_parallel_extract=True, max_workers=0)

        effective, reasons = resolve_effective_workers(4, caps)

        assert effective == 1
        assert "Forced minimum of 1 worker" in reasons[-1]


class TestLogWorkerResolution:
    """Test log_worker_resolution function."""

    def test_no_downgrade_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging when no downgrade occurs."""
        caps = BackendCapabilities(
            supports_parallel_extract=True,
            platform="linux",
            start_method="fork",
            docling_version="1.0.0",
        )

        with caplog.at_level(logging.INFO):
            log_worker_resolution(4, 4, [], caps, pages_to_process=10)

        # Check info message
        assert "using 4 workers for page-level CPU-bound stages" in caplog.text

        # Check debug context
        with caplog.at_level(logging.DEBUG):
            log_worker_resolution(4, 4, [], caps, pages_to_process=10)

        assert "platform=linux" in caplog.text
        assert "start_method=fork" in caplog.text
        assert "docling=1.0.0" in caplog.text
        assert "pages=10" in caplog.text

    def test_downgrade_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging when downgrade occurs."""
        caps = BackendCapabilities(supports_parallel_extract=False)
        reasons = ["Backend does not support parallel page extraction"]

        with caplog.at_level(logging.INFO):
            log_worker_resolution(4, 1, reasons, caps)

        assert "requested 4, using 1 worker" in caplog.text

        with caplog.at_level(logging.WARNING):
            log_worker_resolution(4, 1, reasons, caps)

        assert "Worker downgrade: Backend does not support" in caplog.text

    def test_adjustment_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging for non-critical adjustments."""
        caps = BackendCapabilities(supports_parallel_extract=True, max_workers=2)
        reasons = ["Clamped to backend maximum of 2 workers"]

        with caplog.at_level(logging.INFO):
            log_worker_resolution(4, 2, reasons, caps)

        assert "Worker adjustment: Clamped to backend maximum" in caplog.text

    def test_capability_notes_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging of capability notes."""
        caps = BackendCapabilities(
            supports_parallel_extract=True,
            notes=["Test note 1", "Test note 2"],
        )

        with caplog.at_level(logging.DEBUG):
            log_worker_resolution(2, 2, [], caps)

        assert "Backend capability note: Test note 1" in caplog.text
        assert "Backend capability note: Test note 2" in caplog.text

    def test_singular_worker_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test singular form is used for 1 worker."""
        caps = BackendCapabilities(supports_parallel_extract=False)

        with caplog.at_level(logging.INFO):
            log_worker_resolution(1, 1, [], caps)

        assert "using 1 worker for page-level" in caplog.text
        assert "workers" not in caplog.text.replace("1 worker", "")  # No plural form
