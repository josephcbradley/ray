import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import patch, MagicMock
import pytest
from process_reqs import get_current_platform, get_parser, log_error, run_cmd


def test_get_current_platform():
    with patch("sys.platform", "win32"):
        assert get_current_platform() == "windows"
    with patch("sys.platform", "darwin"):
        assert get_current_platform() == "macos"
    with patch("sys.platform", "linux"):
        assert get_current_platform() == "linux"


def test_arg_parser_defaults():
    parser = get_parser()
    args = parser.parse_args(["sync"])
    assert args.command == "sync"
    assert args.reqs_dir == "reqs"
    assert args.outputs_dir == "outputs"
    assert args.simple_dir == "simple"
    assert args.pyvers == ["3.12", "3.13", "3.14"]


def test_arg_parser_custom_values():
    parser = get_parser()
    args = parser.parse_args([
        "compile",
        "--reqs-dir", "custom_reqs",
        "--outputs-dir", "custom_outs",
        "--simple-dir", "custom_simple",
        "--pyvers", "3.11", "3.12"
    ])
    assert args.command == "compile"
    assert args.reqs_dir == "custom_reqs"
    assert args.outputs_dir == "custom_outs"
    assert args.simple_dir == "custom_simple"
    assert args.pyvers == ["3.11", "3.12"]


def test_log_error(capsys):
    with patch("logging.error") as mock_log:
        log_error("Test Context", "Test Details")
        
        # Verify stderr output
        captured = capsys.readouterr()
        assert "ERROR: Test Context. See error_log.txt for details." in captured.err
        
        # Verify logging call
        mock_log.assert_called_once()
        args, _ = mock_log.call_args
        assert "Test Context" in args[0]
        assert "Test Details" in args[0]


def test_run_cmd_success():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert run_cmd(["ls"], "context") is True
        mock_run.assert_called_once_with(["ls"], capture_output=False, text=False)


def test_run_cmd_failure(capsys):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="Error message")
        # capture_output=True so we can verify the error log detail
        assert run_cmd(["false"], "context", capture_output=True) is False
        
        captured = capsys.readouterr()
        assert "ERROR: context" in captured.err
