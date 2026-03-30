"""
Test CLI functionality and exit codes.
"""

import re
import httpx
import pytest
from unittest.mock import patch
from digest_core.cli import app
from typer.testing import CliRunner


def _strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    return re.sub(r"\x1b\[[0-9;]*[mGKHF]", "", text)


@pytest.fixture
def runner():
    """CLI test runner."""
    return CliRunner()


def test_cli_help(runner):
    """Test CLI help command."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output


def test_cli_run_help(runner):
    """Test CLI run command help."""
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    output = _strip_ansi(result.output)
    assert "from-date" in output
    assert "sources" in output
    assert "out" in output
    assert "model" in output


def test_cli_run_dry_run(runner):
    """Test CLI run with dry-run flag."""
    with patch("digest_core.cli.run_digest_dry_run") as mock_run:
        result = runner.invoke(
            app,
            [
                "run",
                "--from-date",
                "2024-01-15",
                "--sources",
                "ews",
                "--out",
                "/tmp/test",
                "--model",
                "qwen35-397b-a17b",
                "--dry-run",
            ],
        )

        # Dry-run should exit with code 2
        assert result.exit_code == 2
        assert "dry-run" in result.output.lower()
        mock_run.assert_called_once()


def test_cli_run_success(runner):
    """Test CLI run success path."""
    with patch("digest_core.cli.run_digest") as mock_run:
        mock_run.return_value = None

        result = runner.invoke(
            app,
            [
                "run",
                "--from-date",
                "2024-01-15",
                "--sources",
                "ews",
                "--out",
                "/tmp/test",
                "--model",
                "qwen35-397b-a17b",
            ],
        )

        # Should exit with code 0
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_cli_run_with_window(runner):
    """Test CLI run with window parameter."""
    with patch("digest_core.cli.run_digest") as mock_run:
        mock_run.return_value = None

        result = runner.invoke(
            app,
            [
                "run",
                "--from-date",
                "2024-01-15",
                "--sources",
                "ews",
                "--out",
                "/tmp/test",
                "--model",
                "qwen35-397b-a17b",
                "--window",
                "rolling_24h",
            ],
        )

        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_cli_run_with_state(runner):
    """Test CLI run with state parameter."""
    with patch("digest_core.cli.run_digest") as mock_run:
        mock_run.return_value = None

        result = runner.invoke(
            app,
            [
                "run",
                "--from-date",
                "2024-01-15",
                "--sources",
                "ews",
                "--out",
                "/tmp/test",
                "--model",
                "qwen35-397b-a17b",
                "--state",
                "/tmp/state",
            ],
        )

        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_cli_run_invalid_date(runner):
    """Test CLI run with invalid date."""
    result = runner.invoke(
        app,
        [
            "run",
            "--from-date",
            "invalid-date",
            "--sources",
            "ews",
            "--out",
            "/tmp/test",
            "--model",
            "qwen35-397b-a17b",
        ],
    )

    # Should exit with error code
    assert result.exit_code != 0


def test_cli_run_missing_required_args(runner):
    """Test CLI run with missing required arguments."""
    result = runner.invoke(
        app,
        [
            "run",
            "--from-date",
            "2024-01-15",
            # Missing sources, out, model
        ],
    )

    # Should exit with error code
    assert result.exit_code != 0


def test_cli_run_multiple_sources(runner):
    """Test CLI run with multiple sources."""
    with patch("digest_core.cli.run_digest") as mock_run:
        mock_run.return_value = None

        result = runner.invoke(
            app,
            [
                "run",
                "--from-date",
                "2024-01-15",
                "--sources",
                "ews,slack",
                "--out",
                "/tmp/test",
                "--model",
                "qwen35-397b-a17b",
            ],
        )

        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_cli_run_exception_handling(runner):
    """Test CLI run exception handling."""
    with patch("digest_core.cli.run_digest") as mock_run:
        mock_run.side_effect = Exception("Test error")

        result = runner.invoke(
            app,
            [
                "run",
                "--from-date",
                "2024-01-15",
                "--sources",
                "ews",
                "--out",
                "/tmp/test",
                "--model",
                "qwen35-397b-a17b",
            ],
        )

        # Should exit with error code
        assert result.exit_code != 0
        assert "Test error" in result.output


def test_cli_run_config_loading(runner):
    """Test CLI run forwards normalized arguments to the pipeline entrypoint."""
    with patch("digest_core.cli.run_digest") as mock_run:
        mock_run.return_value = None

        result = runner.invoke(
            app,
            [
                "run",
                "--from-date",
                "2024-01-15",
                "--sources",
                "ews,slack",
                "--out",
                "/tmp/test",
                "--model",
                "qwen35-397b-a17b",
            ],
        )

        assert result.exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args.args[:4] == (
            "2024-01-15",
            ["ews", "slack"],
            "/tmp/test",
            "qwen35-397b-a17b",
        )


def test_cli_run_logging(runner):
    """Test CLI run logging setup."""
    with patch("digest_core.cli.setup_logging") as mock_logging:
        with patch("digest_core.cli.run_digest") as mock_run:
            mock_run.return_value = None

            result = runner.invoke(
                app,
                [
                    "run",
                    "--from-date",
                    "2024-01-15",
                    "--sources",
                    "ews",
                    "--out",
                    "/tmp/test",
                    "--model",
                    "qwen35-397b-a17b",
                ],
            )

            assert result.exit_code == 0
            mock_logging.assert_called_once()


def test_cli_mm_ping_help(runner):
    result = runner.invoke(app, ["mm-ping", "--help"])
    assert result.exit_code == 0
    assert "mm-ping" in result.output or "webhook" in result.output.lower()


def test_cli_mm_ping_success(runner, monkeypatch):
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json):
            return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setenv("MM_WEBHOOK_URL", "https://mm.example/hooks/x")
    monkeypatch.setattr("digest_core.deliver.mattermost.httpx.Client", FakeClient)

    result = runner.invoke(app, ["mm-ping"])

    assert result.exit_code == 0
    assert "HTTP 200" in result.output
