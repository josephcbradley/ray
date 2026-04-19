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


def test_full_mirror_flow(temp_workspace):
    # 1. Setup minimal requirements
    test_reqs = temp_workspace / "reqs"
    test_reqs.mkdir()
    (test_reqs / "core.in").write_text("# core content")
    (test_reqs / "base.in").write_text("ipykernel")

    # 2. Build the mirror
    print("Building minimal mirror...")
    script_path = Path(__file__).parent.parent / "process_reqs.py"

    subprocess.run(
        ["uv", "run", "python", str(script_path), str(test_reqs)],
        cwd=temp_workspace,
        check=True,
    )

    outputs_dir = temp_workspace / "outputs"
    if outputs_dir.exists():
        print("Outputs directory contents:")
        for out_file in outputs_dir.iterdir():
            if "windows" in out_file.name:
                print(f"  {out_file.name}:")
                for line in out_file.read_text().splitlines():
                    if "debugpy" in line:
                        print(f"    {line}")

    simple_dir = temp_workspace / "simple"
    assert (simple_dir / "index.html").exists()

    print("Contents of simple directory:")
    for path in simple_dir.rglob("*"):
        if path.is_file() and "debugpy" in path.name:
            print(f"  {path.relative_to(simple_dir)}")

    # 3. Serve the mirror using python -m http.server (handles static PEP 503 correctly)
    port = get_free_port()
    print(f"Starting http.server on port {port}...")
    server_proc = subprocess.Popen(
        ["python", "-m", "http.server", str(port)],
        cwd=simple_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    mirror_url = f"http://localhost:{port}/"

    # Wait for server to be up
    max_retries = 20
    success = False
    while max_retries > 0:
        try:
            r = requests.get(mirror_url, timeout=1)
            if r.status_code == 200:
                success = True
                break
        except Exception:
            pass
        time.sleep(1)
        max_retries -= 1

    if not success:
        server_proc.terminate()
        pytest.fail("Mirror server failed to start")

    try:
        # 4. Try to install a package from the local mirror
        project_dir = temp_workspace / "test_project"
        project_dir.mkdir()
        
        # Create a venv for the install test
        subprocess.run(
            ["uv", "venv"],
            cwd=project_dir,
            check=True,
            capture_output=True,
        )
        
        print("Installing ipykernel from local mirror...")
        result = subprocess.run(
            ["uv", "pip", "install", "ipykernel", "--index-url", mirror_url, "--no-cache"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            pytest.fail("Failed to install package from local mirror")

        print("Successfully installed ipykernel from local mirror!")

    finally:
        server_proc.terminate()
        server_proc.wait()
