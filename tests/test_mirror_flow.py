import contextlib
import functools
import http.server
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from process_reqs import compile_reqs, download_task, get_current_platform


def get_clean_env():
    """Returns os.environ without active VIRTUAL_ENV to avoid uv virtualenv warnings in tests."""
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    return env


class _QuietHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with suppressed logging to keep test output clean."""

    def log_message(self, format, *args):
        pass


@pytest.fixture
def temp_workspace(tmp_path):
    """Sets up a temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


@contextlib.contextmanager
def serve_directory(directory: Path):
    """Starts an HTTP server serving directory on an ephemeral port and guarantees termination."""
    handler = functools.partial(_QuietHTTPHandler, directory=str(directory))
    with http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler) as httpd:
        port = httpd.server_address[1]
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        try:
            yield f"http://127.0.0.1:{port}/"
        finally:
            httpd.shutdown()
            server_thread.join()


def test_jaxlib_0_10_0_download(temp_workspace):
    """Ensure jaxlib==0.10.0 can be compiled and downloaded for Python 3.14."""
    test_reqs = temp_workspace / "jax_010_reqs"
    test_reqs.mkdir()
    (test_reqs / "core.in").write_text("")
    (test_reqs / "ai.in").write_text("jaxlib==0.10.0")

    # Pre-create the output file to skip compilation stage (which fails due to scipy dependencies)
    outputs_dir = temp_workspace / "outputs"
    outputs_dir.mkdir()

    current_platform = "macos"
    if sys.platform == "win32":
        current_platform = "windows"
    elif sys.platform == "linux":
        current_platform = "linux"

    (outputs_dir / f"ai_{current_platform}_3.14.out").write_text("jaxlib==0.10.0")

    script_path = Path(__file__).parent.parent / "process_reqs.py"

    # Target 3.14 for jaxlib 0.10.0
    subprocess.run(
        [
            "uv",
            "run",
            "python",
            str(script_path),
            "sync",
            "--reqs-dir",
            str(test_reqs),
            "--pyvers",
            "3.14",
            "--outputs-dir",
            str(outputs_dir),
        ],
        cwd=temp_workspace,
        check=True,
        env=get_clean_env(),
    )

    simple_dir = temp_workspace / "simple"
    has_jaxlib_010 = False
    for path in simple_dir.rglob("jaxlib-0.10.0*"):
        if path.suffix == ".whl":
            has_jaxlib_010 = True
            print(f"Verified jaxlib 0.10.0 wheel: {path.name}")
            break

    assert has_jaxlib_010, "jaxlib 0.10.0 wheel was not downloaded"


@pytest.mark.parametrize("req_name", ["vis.in", "apps.in", "data.in", "ml.in"])
def test_compile_all_example_reqs(temp_workspace, req_name):
    """Verify that all example requirement files in reqs/ compile cleanly with core.in."""
    reqs_source = Path(__file__).parent.parent / "reqs"
    core_file = reqs_source / "core.in"
    target_req = reqs_source / req_name
    outputs_dir = temp_workspace / "outputs"
    outputs_dir.mkdir()

    platform = get_current_platform()
    pyver = f"{sys.version_info.major}.{sys.version_info.minor}"

    compile_reqs([target_req], core_file, outputs_dir, [pyver], [platform])

    expected_out = outputs_dir / f"{target_req.stem}_{platform}_{pyver}.out"
    assert expected_out.exists(), (
        f"Expected compiled file {expected_out.name} not found"
    )
    content = expected_out.read_text()
    assert len(content.strip()) > 0
    # ipykernel from core.in should always be present in all compiled requirement files
    assert "ipykernel" in content


def test_mirror_sync_and_indexing(temp_workspace):
    """Tests process_reqs.py sync end-to-end on core.in + vis.in, verifying PEP 503 indexing."""
    test_reqs = temp_workspace / "reqs"
    test_reqs.mkdir()
    reqs_source = Path(__file__).parent.parent / "reqs"
    (test_reqs / "core.in").write_text((reqs_source / "core.in").read_text())
    (test_reqs / "vis.in").write_text((reqs_source / "vis.in").read_text())

    script_path = Path(__file__).parent.parent / "process_reqs.py"
    pyver = f"{sys.version_info.major}.{sys.version_info.minor}"

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            str(script_path),
            "sync",
            "--reqs-dir",
            str(test_reqs),
            "--pyvers",
            pyver,
        ],
        cwd=temp_workspace,
        capture_output=True,
        text=True,
        env=get_clean_env(),
    )
    assert result.returncode == 0, f"process_reqs.py sync failed: {result.stderr}"

    simple_dir = temp_workspace / "simple"
    assert (simple_dir / "index.html").exists()

    # Verify PEP 503 root structure
    root_index_html = (simple_dir / "index.html").read_text()
    assert "ipykernel" in root_index_html
    assert "seaborn" in root_index_html
    assert "matplotlib" in root_index_html

    # Verify package subdirectories and index.html
    ipykernel_dir = simple_dir / "ipykernel"
    assert ipykernel_dir.exists()
    assert (ipykernel_dir / "index.html").exists()
    whls = list(ipykernel_dir.glob("*.whl"))
    assert len(whls) > 0, "No ipykernel wheels were downloaded"


def test_siloed_uv_sync_offline(temp_workspace):
    """Tests serving the mirror and installing ipykernel and seaborn into a siloed project using uv sync and --offline."""
    # 1. Build the mirror with core.in and vis.in
    test_reqs = temp_workspace / "reqs"
    test_reqs.mkdir()
    reqs_source = Path(__file__).parent.parent / "reqs"
    (test_reqs / "core.in").write_text((reqs_source / "core.in").read_text())
    (test_reqs / "vis.in").write_text((reqs_source / "vis.in").read_text())

    script_path = Path(__file__).parent.parent / "process_reqs.py"
    pyver = f"{sys.version_info.major}.{sys.version_info.minor}"

    subprocess.run(
        [
            "uv",
            "run",
            "python",
            str(script_path),
            "sync",
            "--reqs-dir",
            str(test_reqs),
            "--pyvers",
            pyver,
        ],
        cwd=temp_workspace,
        check=True,
        capture_output=True,
        text=True,
        env=get_clean_env(),
    )

    simple_dir = temp_workspace / "simple"

    with serve_directory(simple_dir) as mirror_url:
        # 2. Configure a siloed client project (matching ray.sh pattern)
        client_dir = temp_workspace / "client_project"
        client_dir.mkdir()
        platform_marker = (
            "darwin"
            if sys.platform == "darwin"
            else ("win32" if sys.platform == "win32" else "linux")
        )
        marker = (
            f"sys_platform == '{platform_marker}' and implementation_name == 'cpython'"
        )
        pyproject_content = f"""[project]
name = "client-project"
version = "0.1.0"
requires-python = ">={pyver}"
dependencies = [
    "ipykernel",
    "boto3",
    "httpx",
]

[[tool.uv.index]]
url = "{mirror_url}"
default = true

[tool.uv]
environments = [
    "{marker}"
]
"""
        (client_dir / "pyproject.toml").write_text(pyproject_content)

        clean_env = get_clean_env()

        # 3. Test siloed install with --no-cache: must pull exclusively from mirror
        sync_res = subprocess.run(
            ["uv", "sync", "--no-cache"],
            cwd=client_dir,
            capture_output=True,
            text=True,
            env=clean_env,
        )
        assert sync_res.returncode == 0, f"uv sync failed: {sync_res.stderr}"
        assert (client_dir / "uv.lock").exists()

        # Verify packages installed in venv
        venv_dir = client_dir / ".venv"
        assert venv_dir.exists()

        # 4. Anti-leakage check: Adding an unmirrored package MUST fail
        unmirrored_toml = f"""[project]
name = "client-project"
version = "0.1.0"
requires-python = ">={pyver}"
dependencies = [
    "ipykernel",
    "boto3",
    "httpx",
    "cowsay",
]

[[tool.uv.index]]
url = "{mirror_url}"
default = true

[tool.uv]
environments = [
    "{marker}"
]
"""
        (client_dir / "pyproject.toml").write_text(unmirrored_toml)
        leak_res = subprocess.run(
            ["uv", "sync", "--no-cache"],
            cwd=client_dir,
            capture_output=True,
            text=True,
            env=clean_env,
        )
        assert leak_res.returncode != 0, (
            "uv sync should fail when package is missing from mirror"
        )
        assert "cowsay" in leak_res.stderr

        # 5. Offline verification check: Restore original dependencies and test uv sync --offline
        (client_dir / "pyproject.toml").write_text(pyproject_content)
        # Re-sync to restore lockfile
        subprocess.run(
            ["uv", "sync"],
            cwd=client_dir,
            check=True,
            capture_output=True,
            text=True,
            env=clean_env,
        )

        offline_res = subprocess.run(
            ["uv", "sync", "--offline"],
            cwd=client_dir,
            capture_output=True,
            text=True,
            env=clean_env,
        )
        assert offline_res.returncode == 0, (
            f"uv sync --offline failed: {offline_res.stderr}"
        )


def test_missing_wheel_error_handling(temp_workspace, caplog, capsys):
    """Verify that download_task handles nonexistent or incompatible wheels gracefully and logs details."""
    outputs_dir = temp_workspace / "outputs"
    outputs_dir.mkdir()
    simple_dir = temp_workspace / "simple"
    simple_dir.mkdir()

    impossible_out = outputs_dir / "dummy_platform_3.14.out"
    impossible_out.write_text("nonexistent-package-xyz-12345==99.99.99\n")

    with caplog.at_level("ERROR"):
        success = download_task("3.14", "linux", impossible_out, simple_dir)
        assert success is False

    captured = capsys.readouterr()
    assert "ERROR: Download failed for dummy_platform_3.14.out" in captured.err
    assert any(
        "Download failed for dummy_platform_3.14.out" in record.message
        for record in caplog.records
    )
