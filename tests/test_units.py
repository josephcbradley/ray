import os
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from process_reqs import (
    download_task,
    get_current_platform,
    get_parser,
    index_reqs,
    log_error,
    main,
    run_cmd,
)


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
    args = parser.parse_args(
        [
            "compile",
            "--reqs-dir",
            "custom_reqs",
            "--outputs-dir",
            "custom_outs",
            "--simple-dir",
            "custom_simple",
            "--pyvers",
            "3.11",
            "3.12",
        ]
    )
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


def test_index_reqs():
    with patch("process_reqs.run_cmd") as mock_run:
        mock_run.return_value = True
        simple_dir = Path("/tmp/test_simple")
        index_reqs(simple_dir)
        mock_run.assert_called_once_with(
            ["uvx", "simple503", "--sort", str(simple_dir)],
            "Failed to generate simple503 index",
            capture_output=False,
        )


def test_download_task_platform_tags_linux():
    with patch("process_reqs.run_cmd") as mock_run:
        mock_run.return_value = True
        out_file = Path("/tmp/core_linux_3.12.out")
        simple_dir = Path("/tmp/simple")
        download_task("3.12", "linux", out_file, simple_dir)

        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        assert "--abi" in cmd
        assert "cp312" in cmd
        assert "--platform" in cmd
        assert "manylinux_2_34_x86_64" in cmd
        assert "manylinux_2_17_x86_64" in cmd
        assert "manylinux_2_17_aarch64" in cmd


def test_download_task_platform_tags_macos():
    with patch("process_reqs.run_cmd") as mock_run:
        mock_run.return_value = True
        out_file = Path("/tmp/core_macos_3.14.out")
        simple_dir = Path("/tmp/simple")
        download_task("3.14", "macos", out_file, simple_dir)

        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        assert "--abi" in cmd
        assert "cp314" in cmd
        assert "--platform" in cmd
        assert "macosx_10_12_x86_64" in cmd
        assert "macosx_11_0_arm64" in cmd


def test_download_task_platform_tags_windows():
    with patch("process_reqs.run_cmd") as mock_run:
        mock_run.return_value = True
        out_file = Path("/tmp/core_windows_3.13.out")
        simple_dir = Path("/tmp/simple")
        download_task("3.13", "windows", out_file, simple_dir)

        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        assert "--abi" in cmd
        assert "cp313" in cmd
        assert "--platform" in cmd
        assert "win_amd64" in cmd


def test_main_subcommand_compile():
    with (
        patch(
            "sys.argv",
            [
                "process_reqs.py",
                "compile",
                "--reqs-dir",
                "reqs",
                "--pyvers",
                "3.14",
            ],
        ),
        patch("process_reqs.compile_reqs") as mock_compile,
    ):
        main()
        assert mock_compile.called


def test_main_subcommand_index():
    with (
        patch("sys.argv", ["process_reqs.py", "index", "--simple-dir", "simple"]),
        patch("process_reqs.index_reqs") as mock_index,
    ):
        main()
        mock_index.assert_called_once_with(Path("simple"))
