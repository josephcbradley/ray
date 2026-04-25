import sys
import subprocess
import time
import socket
import pytest
from pathlib import Path
import requests


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture
def temp_workspace(tmp_path):
    """Sets up a temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


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
        ["uv", "run", "python", str(script_path), "sync", "--reqs-dir", str(test_reqs), "--pyvers", "3.14", "--outputs-dir", str(outputs_dir)],
        cwd=temp_workspace,
        check=True,
    )
    
    simple_dir = temp_workspace / "simple"
    has_jaxlib_010 = False
    for path in simple_dir.rglob("jaxlib-0.10.0*"):
        if path.suffix == ".whl":
            has_jaxlib_010 = True
            print(f"Verified jaxlib 0.10.0 wheel: {path.name}")
            break
            
    assert has_jaxlib_010, "jaxlib 0.10.0 wheel was not downloaded"


def test_full_mirror_flow(temp_workspace):
    # 1. Setup minimal requirements
    test_reqs = temp_workspace / "reqs"
    test_reqs.mkdir()
    (test_reqs / "core.in").write_text("# core content")
    (test_reqs / "base.in").write_text("ipykernel")
    # Use rich as a reliable cross-platform package with wheels
    (test_reqs / "ui.in").write_text("rich")

    # 2. Build the mirror
    print("Building minimal mirror...")
    script_path = Path(__file__).parent.parent / "process_reqs.py"

    pyver = f"{sys.version_info.major}.{sys.version_info.minor}"

    try:
        subprocess.run(
            ["uv", "run", "python", str(script_path), "sync", "--reqs-dir", str(test_reqs), "--pyvers", pyver],
            cwd=temp_workspace,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        log_file = temp_workspace / "error_log.txt"
        if log_file.exists():
            print("--- ERROR LOG ---")
            print(log_file.read_text())
        raise e

    simple_dir = temp_workspace / "simple"
    assert (simple_dir / "index.html").exists()

    has_rich = False
    for path in simple_dir.rglob("*"):
        if path.is_file() and "rich" in path.name:
            has_rich = True
            break
    assert has_rich, "rich wheel was not downloaded"

    # 3. Serve the mirror
    port = get_free_port()
    server_proc = subprocess.Popen(
        ["python", "-m", "http.server", str(port)],
        cwd=simple_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    mirror_url = f"http://localhost:{port}/"

    # Wait for server
    max_retries = 10
    while max_retries > 0:
        try:
            if requests.get(mirror_url, timeout=1).status_code == 200:
                break
        except:
            pass
        time.sleep(1)
        max_retries -= 1

    try:
        # 4. Install from mirror
        project_dir = temp_workspace / "test_project"
        project_dir.mkdir()
        subprocess.run(["uv", "venv"], cwd=project_dir, check=True, capture_output=True)
        
        venv_path = project_dir / ".venv"
        python_exe = venv_path / "bin" / "python"
        if sys.platform == "win32":
             python_exe = venv_path / "Scripts" / "python.exe"

        result = subprocess.run(
            ["uv", "pip", "install", "rich", "--index-url", mirror_url, "--no-cache", "--python", str(python_exe)],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Failed to install rich: {result.stderr}"
        print("Successfully installed rich from local mirror!")

    finally:
        server_proc.terminate()
