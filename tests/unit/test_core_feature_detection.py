"""Tests for core feature detection module."""

from __future__ import annotations

import logging
from unittest.mock import Mock, patch

import pytest

from pdf2foundry.core.feature_detection import FeatureAvailability


class TestFeatureAvailability:
    """Test the FeatureAvailability class methods."""

    def test_has_ml_support_with_env_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test ML support detection when disabled via environment variable."""
        monkeypatch.setenv("PDF2FOUNDRY_NO_ML", "1")

        result = FeatureAvailability.has_ml_support()

        assert result is False

    def test_has_ml_support_with_available_imports(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test ML support detection when imports are available."""
        # Ensure env var is not set
        monkeypatch.delenv("PDF2FOUNDRY_NO_ML", raising=False)

        with patch.dict("sys.modules", {"torch": Mock(), "transformers": Mock()}):
            result = FeatureAvailability.has_ml_support()

        assert result is True

    def test_has_ml_support_with_missing_torch(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test ML support detection when torch is missing."""
        monkeypatch.delenv("PDF2FOUNDRY_NO_ML", raising=False)

        with patch("builtins.__import__") as mock_import:

            def side_effect(name: str, *args, **kwargs):
                if name == "torch":
                    raise ImportError("No module named 'torch'")
                return Mock()

            mock_import.side_effect = side_effect

            with caplog.at_level(logging.DEBUG):
                result = FeatureAvailability.has_ml_support()

        assert result is False
        assert "ML support not available - transformers or torch not found" in caplog.text

    def test_has_ml_support_with_missing_transformers(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test ML support detection when transformers is missing."""
        monkeypatch.delenv("PDF2FOUNDRY_NO_ML", raising=False)

        with patch("builtins.__import__") as mock_import:

            def side_effect(name: str, *args, **kwargs):
                if name == "transformers":
                    raise ImportError("No module named 'transformers'")
                return Mock()

            mock_import.side_effect = side_effect

            with caplog.at_level(logging.DEBUG):
                result = FeatureAvailability.has_ml_support()

        assert result is False
        assert "ML support not available - transformers or torch not found" in caplog.text

    def test_has_ocr_support_with_available_import(self) -> None:
        """Test OCR support detection when pytesseract is available."""
        with patch.dict("sys.modules", {"pytesseract": Mock()}):
            result = FeatureAvailability.has_ocr_support()

        assert result is True

    def test_has_ocr_support_with_missing_import(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test OCR support detection when pytesseract is missing."""
        with patch("builtins.__import__") as mock_import:

            def side_effect(name: str, *args, **kwargs):
                if name == "pytesseract":
                    raise ImportError("No module named 'pytesseract'")
                return Mock()

            mock_import.side_effect = side_effect

            with caplog.at_level(logging.DEBUG):
                result = FeatureAvailability.has_ocr_support()

        assert result is False
        assert "OCR support not available - pytesseract not found" in caplog.text

    def test_is_ci_minimal_environment_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test CI minimal environment detection when both env vars are set."""
        monkeypatch.setenv("CI", "1")
        monkeypatch.setenv("PDF2FOUNDRY_CI_MINIMAL", "1")

        result = FeatureAvailability.is_ci_minimal_environment()

        assert result is True

    def test_is_ci_minimal_environment_false_no_ci(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test CI minimal environment detection when CI is not set."""
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.setenv("PDF2FOUNDRY_CI_MINIMAL", "1")

        result = FeatureAvailability.is_ci_minimal_environment()

        assert result is False

    def test_is_ci_minimal_environment_false_no_minimal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test CI minimal environment detection when CI_MINIMAL is not set."""
        monkeypatch.setenv("CI", "1")
        monkeypatch.delenv("PDF2FOUNDRY_CI_MINIMAL", raising=False)

        result = FeatureAvailability.is_ci_minimal_environment()

        assert result is False

    def test_is_ci_minimal_environment_false_wrong_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test CI minimal environment detection with wrong values."""
        monkeypatch.setenv("CI", "0")
        monkeypatch.setenv("PDF2FOUNDRY_CI_MINIMAL", "0")

        result = FeatureAvailability.is_ci_minimal_environment()

        assert result is False

    def test_get_available_features_all_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting all available features when everything is available."""
        monkeypatch.delenv("PDF2FOUNDRY_NO_ML", raising=False)
        monkeypatch.setenv("CI", "1")
        monkeypatch.setenv("PDF2FOUNDRY_CI_MINIMAL", "1")

        with patch.dict("sys.modules", {"torch": Mock(), "transformers": Mock(), "pytesseract": Mock()}):
            result = FeatureAvailability.get_available_features()

        expected = {
            "ml": True,
            "ocr": True,
            "ci_minimal": True,
            "environment": {
                "ci": True,
                "ci_minimal": True,
            },
        }

        assert result == expected

    def test_get_available_features_mixed_availability(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting available features with mixed availability."""
        monkeypatch.setenv("PDF2FOUNDRY_NO_ML", "1")  # ML disabled
        monkeypatch.setenv("CI", "0")  # Not in CI
        monkeypatch.delenv("PDF2FOUNDRY_CI_MINIMAL", raising=False)

        with patch.dict("sys.modules", {"pytesseract": Mock()}):
            result = FeatureAvailability.get_available_features()

        expected = {
            "ml": False,  # Disabled via env var
            "ocr": True,  # Available
            "ci_minimal": False,  # Not in CI minimal mode
            "environment": {
                "ci": False,
                "ci_minimal": False,
            },
        }

        assert result == expected

    def test_get_available_features_nothing_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting available features when nothing is available."""
        monkeypatch.setenv("PDF2FOUNDRY_NO_ML", "1")
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("PDF2FOUNDRY_CI_MINIMAL", raising=False)

        with patch("builtins.__import__") as mock_import:

            def side_effect(name: str, *args, **kwargs):
                if name in ("torch", "transformers", "pytesseract"):
                    raise ImportError(f"No module named '{name}'")
                return Mock()

            mock_import.side_effect = side_effect

            result = FeatureAvailability.get_available_features()

        expected = {
            "ml": False,
            "ocr": False,
            "ci_minimal": False,
            "environment": {
                "ci": False,
                "ci_minimal": False,
            },
        }

        assert result == expected

    def test_log_feature_status_all_available(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test logging feature status when all features are available."""
        monkeypatch.delenv("PDF2FOUNDRY_NO_ML", raising=False)
        monkeypatch.setenv("CI", "1")
        monkeypatch.setenv("PDF2FOUNDRY_CI_MINIMAL", "1")

        with (
            patch.dict("sys.modules", {"torch": Mock(), "transformers": Mock(), "pytesseract": Mock()}),
            caplog.at_level(logging.INFO),
        ):
            FeatureAvailability.log_feature_status()

        assert "Feature availability status:" in caplog.text
        assert "ML support: True" in caplog.text
        assert "OCR support: True" in caplog.text
        assert "CI minimal mode: True" in caplog.text
        assert "Environment - CI: True" in caplog.text
        assert "Environment - CI minimal: True" in caplog.text

    def test_log_feature_status_mixed_availability(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test logging feature status with mixed availability."""
        monkeypatch.setenv("PDF2FOUNDRY_NO_ML", "1")
        monkeypatch.setenv("CI", "0")
        monkeypatch.delenv("PDF2FOUNDRY_CI_MINIMAL", raising=False)

        with patch("builtins.__import__") as mock_import:

            def side_effect(name: str, *args, **kwargs):
                if name == "pytesseract":
                    raise ImportError("No module named 'pytesseract'")
                return Mock()

            mock_import.side_effect = side_effect

            with caplog.at_level(logging.INFO):
                FeatureAvailability.log_feature_status()

        assert "Feature availability status:" in caplog.text
        assert "ML support: False" in caplog.text
        assert "OCR support: False" in caplog.text
        assert "CI minimal mode: False" in caplog.text
        assert "Environment - CI: False" in caplog.text
        assert "Environment - CI minimal: False" in caplog.text

    def test_ml_support_debug_logging_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test debug logging when ML support is disabled via flag."""
        monkeypatch.setenv("PDF2FOUNDRY_NO_ML", "1")

        with caplog.at_level(logging.DEBUG):
            result = FeatureAvailability.has_ml_support()

        assert result is False
        assert "ML support disabled via --no-ml flag" in caplog.text

    def test_environment_variables_edge_cases(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test edge cases with environment variable values."""
        # Test with different values that should be falsy
        test_cases = [
            ("0", "0", False),
            ("false", "false", False),
            ("", "", False),
            ("1", "0", False),
            ("0", "1", False),
            ("yes", "yes", False),  # Only "1" should be truthy
        ]

        for ci_val, minimal_val, expected in test_cases:
            monkeypatch.setenv("CI", ci_val)
            monkeypatch.setenv("PDF2FOUNDRY_CI_MINIMAL", minimal_val)

            result = FeatureAvailability.is_ci_minimal_environment()
            assert result == expected, f"CI={ci_val}, MINIMAL={minimal_val} should return {expected}"

    def test_get_available_features_environment_section_consistency(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment section in get_available_features is consistent with is_ci_minimal_environment."""
        test_cases = [
            ("1", "1", True, True, True),  # Both set to "1" -> ci_minimal should be True
            ("1", "0", True, False, False),  # Only CI set -> ci_minimal should be False
            ("0", "1", False, True, False),  # Only MINIMAL set -> ci_minimal should be False
            ("0", "0", False, False, False),  # Neither set -> ci_minimal should be False
        ]

        for ci_val, minimal_val, expected_ci, expected_ci_minimal_env, expected_ci_minimal_combined in test_cases:
            monkeypatch.setenv("CI", ci_val)
            monkeypatch.setenv("PDF2FOUNDRY_CI_MINIMAL", minimal_val)

            features = FeatureAvailability.get_available_features()
            ci_minimal_direct = FeatureAvailability.is_ci_minimal_environment()

            assert features["environment"]["ci"] == expected_ci
            assert features["environment"]["ci_minimal"] == expected_ci_minimal_env
            assert features["ci_minimal"] == ci_minimal_direct
            assert features["ci_minimal"] == expected_ci_minimal_combined
            assert features["ci_minimal"] == (expected_ci and expected_ci_minimal_env)
