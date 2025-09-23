"""Tests for core timeout utilities."""

from __future__ import annotations

import logging
import os
import signal
import threading
import time
from unittest.mock import patch

import pytest

from pdf2foundry.core.timeout import get_environment_timeout, timeout_context


class TestTimeoutContext:
    """Test the timeout_context context manager."""

    @pytest.mark.skipif(os.name == "nt", reason="Signals not supported on Windows")
    def test_timeout_context_successful_operation(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test timeout context with operation that completes within timeout."""
        with caplog.at_level(logging.DEBUG), timeout_context(5, "test operation"):
            time.sleep(0.1)  # Short operation

        assert "Starting test operation with 5s timeout" in caplog.text
        assert "Completed test operation within timeout" in caplog.text

    @pytest.mark.skipif(os.name == "nt", reason="Signals not supported on Windows")
    def test_timeout_context_timeout_occurs(self) -> None:
        """Test timeout context when operation times out."""
        with (
            pytest.raises(TimeoutError, match="test operation timed out after 1 seconds"),
            timeout_context(1, "test operation"),
        ):
            time.sleep(2)  # Long operation that should timeout

    @pytest.mark.skipif(os.name == "nt", reason="Signals not supported on Windows")
    def test_timeout_context_exception_during_operation(self) -> None:
        """Test timeout context when operation raises an exception."""
        with pytest.raises(ValueError, match="test error"), timeout_context(5, "test operation"):
            raise ValueError("test error")

    @pytest.mark.skipif(os.name == "nt", reason="Signals not supported on Windows")
    def test_timeout_context_cleanup_on_success(self) -> None:
        """Test that timeout context properly cleans up signal handlers on success."""
        # Get original handler
        original_handler = signal.signal(signal.SIGALRM, signal.SIG_DFL)

        try:
            with timeout_context(5, "test operation"):
                # Check that a custom handler is set
                current_handler = signal.signal(signal.SIGALRM, signal.SIG_DFL)
                signal.signal(signal.SIGALRM, current_handler)  # Restore
                assert current_handler != signal.SIG_DFL

            # After context, should be cleaned up
            final_handler = signal.signal(signal.SIGALRM, signal.SIG_DFL)
            signal.signal(signal.SIGALRM, final_handler)  # Restore
            # Handler should be restored (though might not be exactly the same object)

        finally:
            # Ensure we restore the original handler
            signal.signal(signal.SIGALRM, original_handler)

    @pytest.mark.skipif(os.name == "nt", reason="Signals not supported on Windows")
    def test_timeout_context_cleanup_on_exception(self) -> None:
        """Test that timeout context properly cleans up signal handlers on exception."""
        # Get original handler
        original_handler = signal.signal(signal.SIGALRM, signal.SIG_DFL)

        try:
            with pytest.raises(ValueError), timeout_context(5, "test operation"):
                raise ValueError("test error")

            # After context, should be cleaned up even after exception
            final_handler = signal.signal(signal.SIGALRM, signal.SIG_DFL)
            signal.signal(signal.SIGALRM, final_handler)  # Restore

        finally:
            # Ensure we restore the original handler
            signal.signal(signal.SIGALRM, original_handler)

    def test_timeout_context_windows_fallback(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test timeout context fallback on Windows (no signal support)."""
        with patch("os.name", "nt"):
            with caplog.at_level(logging.WARNING), timeout_context(5, "test operation"):
                time.sleep(0.1)

            assert "Timeout protection not available on this platform for test operation" in caplog.text

    def test_timeout_context_no_sigalrm_fallback(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test timeout context fallback when SIGALRM is not available."""
        # Temporarily remove SIGALRM from signal module
        original_sigalrm = getattr(signal, "SIGALRM", None)
        if hasattr(signal, "SIGALRM"):
            delattr(signal, "SIGALRM")

        try:
            with caplog.at_level(logging.WARNING), timeout_context(5, "test operation"):
                time.sleep(0.1)

            assert "Timeout protection not available on this platform for test operation" in caplog.text
        finally:
            # Restore SIGALRM if it existed
            if original_sigalrm is not None:
                signal.SIGALRM = original_sigalrm

    @pytest.mark.skipif(os.name == "nt", reason="Signals not supported on Windows")
    def test_timeout_context_non_main_thread_fallback(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test timeout context fallback when not in main thread."""
        result = []

        def thread_function():
            with caplog.at_level(logging.WARNING), timeout_context(5, "test operation"):
                time.sleep(0.1)
                result.append("completed")

        thread = threading.Thread(target=thread_function)
        thread.start()
        thread.join()

        assert result == ["completed"]
        assert "Timeout protection not available in non-main thread for test operation" in caplog.text

    @pytest.mark.skipif(os.name == "nt", reason="Signals not supported on Windows")
    def test_timeout_handler_function(self) -> None:
        """Test the timeout handler function directly."""
        # This is a bit tricky to test directly, but we can test the timeout behavior
        with (
            pytest.raises(TimeoutError, match="quick test timed out after 1 seconds"),
            timeout_context(1, "quick test"),
        ):
            time.sleep(2)

    def test_timeout_context_default_operation_name(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test timeout context with default operation name."""
        with patch("os.name", "nt"):  # Use Windows to avoid actual timeout
            with caplog.at_level(logging.WARNING), timeout_context(5):  # No operation name provided
                pass

            assert "Timeout protection not available on this platform for operation" in caplog.text


class TestGetEnvironmentTimeout:
    """Test the get_environment_timeout function."""

    def test_get_environment_timeout_with_specific_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test timeout retrieval with operation-specific environment variable."""
        monkeypatch.setenv("PDF2FOUNDRY_MODEL_LOAD_TIMEOUT", "120")

        result = get_environment_timeout("model_load")

        assert result == 120

    def test_get_environment_timeout_invalid_env_var(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test timeout retrieval with invalid environment variable value."""
        monkeypatch.setenv("PDF2FOUNDRY_OCR_PROCESS_TIMEOUT", "invalid")
        monkeypatch.delenv("CI", raising=False)

        with caplog.at_level(logging.WARNING):
            result = get_environment_timeout("ocr_process", default_local=300, default_ci=60)

        assert result == 300  # Should use local default
        assert "Invalid timeout value in PDF2FOUNDRY_OCR_PROCESS_TIMEOUT: invalid, using defaults" in caplog.text

    def test_get_environment_timeout_ci_environment(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test timeout retrieval in CI environment."""
        monkeypatch.setenv("CI", "1")
        monkeypatch.delenv("PDF2FOUNDRY_TEST_TIMEOUT", raising=False)

        with caplog.at_level(logging.DEBUG):
            result = get_environment_timeout("test", default_local=300, default_ci=60)

        assert result == 60
        assert "Using CI timeout for test: 60s" in caplog.text

    def test_get_environment_timeout_local_environment(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test timeout retrieval in local environment."""
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("PDF2FOUNDRY_PROCESSING_TIMEOUT", raising=False)

        with caplog.at_level(logging.DEBUG):
            result = get_environment_timeout("processing", default_local=300, default_ci=60)

        assert result == 300
        assert "Using local timeout for processing: 300s" in caplog.text

    def test_get_environment_timeout_ci_false(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test timeout retrieval when CI is set to false."""
        monkeypatch.setenv("CI", "0")
        monkeypatch.delenv("PDF2FOUNDRY_BUILD_TIMEOUT", raising=False)

        with caplog.at_level(logging.DEBUG):
            result = get_environment_timeout("build", default_local=600, default_ci=120)

        assert result == 600  # Should use local default
        assert "Using local timeout for build: 600s" in caplog.text

    def test_get_environment_timeout_env_var_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment variable takes priority over CI/local defaults."""
        monkeypatch.setenv("CI", "1")  # CI environment
        monkeypatch.setenv("PDF2FOUNDRY_CUSTOM_TIMEOUT", "999")  # Custom timeout

        result = get_environment_timeout("custom", default_local=300, default_ci=60)

        assert result == 999  # Should use env var, not CI default

    def test_get_environment_timeout_operation_name_case_conversion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that operation names are properly converted to uppercase for env vars."""
        monkeypatch.setenv("PDF2FOUNDRY_MODEL_LOADING_TEST_TIMEOUT", "180")

        result = get_environment_timeout("model_loading_test")

        assert result == 180

    def test_get_environment_timeout_default_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default timeout values."""
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("PDF2FOUNDRY_DEFAULT_TEST_TIMEOUT", raising=False)

        # Test with default parameters
        result = get_environment_timeout("default_test")

        assert result == 300  # Default local value

    def test_get_environment_timeout_ci_default_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test default CI timeout values."""
        monkeypatch.setenv("CI", "1")
        monkeypatch.delenv("PDF2FOUNDRY_CI_TEST_TIMEOUT", raising=False)

        # Test with default parameters
        result = get_environment_timeout("ci_test")

        assert result == 60  # Default CI value

    def test_get_environment_timeout_zero_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test timeout with zero value (should be valid)."""
        monkeypatch.setenv("PDF2FOUNDRY_ZERO_TIMEOUT", "0")

        result = get_environment_timeout("zero")

        assert result == 0

    def test_get_environment_timeout_negative_value(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test timeout with negative value (should use defaults)."""
        monkeypatch.setenv("PDF2FOUNDRY_NEGATIVE_TIMEOUT", "-10")
        monkeypatch.delenv("CI", raising=False)

        result = get_environment_timeout("negative", default_local=300, default_ci=60)

        # Negative values should be accepted as valid integers
        assert result == -10

    def test_get_environment_timeout_empty_string(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test timeout with empty string value."""
        monkeypatch.setenv("PDF2FOUNDRY_EMPTY_TIMEOUT", "")
        monkeypatch.delenv("CI", raising=False)

        with caplog.at_level(logging.WARNING):
            result = get_environment_timeout("empty", default_local=300, default_ci=60)

        assert result == 300  # Should use local default
        assert "Invalid timeout value in PDF2FOUNDRY_EMPTY_TIMEOUT: , using defaults" in caplog.text

    def test_get_environment_timeout_float_value(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test timeout with float value (should be invalid)."""
        monkeypatch.setenv("PDF2FOUNDRY_FLOAT_TIMEOUT", "30.5")
        monkeypatch.delenv("CI", raising=False)

        with caplog.at_level(logging.WARNING):
            result = get_environment_timeout("float", default_local=300, default_ci=60)

        assert result == 300  # Should use local default
        assert "Invalid timeout value in PDF2FOUNDRY_FLOAT_TIMEOUT: 30.5, using defaults" in caplog.text

    def test_get_environment_timeout_very_large_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test timeout with very large value."""
        monkeypatch.setenv("PDF2FOUNDRY_LARGE_TIMEOUT", "999999")

        result = get_environment_timeout("large")

        assert result == 999999

    def test_get_environment_timeout_multiple_operations(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test timeout retrieval for multiple different operations."""
        monkeypatch.setenv("PDF2FOUNDRY_OP1_TIMEOUT", "100")
        monkeypatch.setenv("PDF2FOUNDRY_OP2_TIMEOUT", "200")
        monkeypatch.setenv("CI", "1")

        result1 = get_environment_timeout("op1", default_local=300, default_ci=60)
        result2 = get_environment_timeout("op2", default_local=300, default_ci=60)
        result3 = get_environment_timeout("op3", default_local=300, default_ci=60)  # No env var

        assert result1 == 100  # From env var
        assert result2 == 200  # From env var
        assert result3 == 60  # CI default


class TestIntegrationScenarios:
    """Test integration scenarios combining timeout_context and get_environment_timeout."""

    @pytest.mark.skipif(os.name == "nt", reason="Signals not supported on Windows")
    def test_timeout_context_with_environment_timeout(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test using timeout_context with timeout from get_environment_timeout."""
        monkeypatch.setenv("PDF2FOUNDRY_INTEGRATION_TEST_TIMEOUT", "2")

        timeout_value = get_environment_timeout("integration_test")
        assert timeout_value == 2

        with caplog.at_level(logging.DEBUG), timeout_context(timeout_value, "integration test"):
            time.sleep(0.1)

        assert "Starting integration test with 2s timeout" in caplog.text
        assert "Completed integration test within timeout" in caplog.text

    def test_timeout_context_fallback_with_environment_timeout(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test timeout_context fallback behavior with environment-configured timeout."""
        monkeypatch.setenv("PDF2FOUNDRY_FALLBACK_TEST_TIMEOUT", "5")

        timeout_value = get_environment_timeout("fallback_test")
        assert timeout_value == 5

        with (
            patch("os.name", "nt"),  # Simulate Windows
            caplog.at_level(logging.WARNING),
            timeout_context(timeout_value, "fallback test"),
        ):
            time.sleep(0.1)

        assert "Timeout protection not available on this platform for fallback test" in caplog.text

    def test_ci_environment_integration(self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
        """Test integration in CI environment with shorter timeouts."""
        monkeypatch.setenv("CI", "1")

        with caplog.at_level(logging.DEBUG):
            timeout_value = get_environment_timeout("ci_integration", default_local=300, default_ci=30)
            assert timeout_value == 30  # CI default

            with (
                patch("os.name", "nt"),  # Use Windows to avoid actual timeout
                timeout_context(timeout_value, "CI integration test"),
            ):
                pass

        assert "Using CI timeout for ci_integration: 30s" in caplog.text
        assert "Timeout protection not available on this platform for CI integration test" in caplog.text

    def test_local_environment_integration(self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
        """Test integration in local environment with longer timeouts."""
        monkeypatch.delenv("CI", raising=False)

        with caplog.at_level(logging.DEBUG):
            timeout_value = get_environment_timeout("local_integration", default_local=600, default_ci=60)
            assert timeout_value == 600  # Local default

            with (
                patch("os.name", "nt"),  # Use Windows to avoid actual timeout
                timeout_context(timeout_value, "local integration test"),
            ):
                pass

        assert "Using local timeout for local_integration: 600s" in caplog.text
        assert "Timeout protection not available on this platform for local integration test" in caplog.text
