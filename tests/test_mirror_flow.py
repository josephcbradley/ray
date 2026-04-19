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
    # We use ipykernel as requested. It has many dependencies (debugpy, etc.)
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

    assert (temp_workspace / "simple" / "index.html").exists()

    # 3. Serve the mirror
    port = get_free_port()
    print(f"Starting pypiserver on port {port}...")
    root_dir = Path(__file__).parent.parent.absolute()
    print(f"Project root: {root_dir}")
    server_proc = subprocess.Popen(
        [
            "uv",
            "run",
            "python",
            "-m",
            "pypiserver",
            "run",
            "-p",
            str(port),
            str(temp_workspace / "simple"),
        ],
        cwd=root_dir,
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
        # 4. Try to add a package from a new env
        project_dir = temp_workspace / "test_project"
        subprocess.run(["uv", "init", "test_project"], cwd=temp_workspace, check=True)

        toml_path = project_dir / "pyproject.toml"
        with open(toml_path, "a") as f:
            f.write(f'\n[[tool.uv.index]]\nurl="{mirror_url}"\ndefault=true\n')
            f.write(
                "\n[tool.uv]\nenvironments = [\"sys_platform == 'linux'\", \"sys_platform == 'windows'\"]\n"
            )

        # 5. Run uv add
        # We use --no-cache to force it to hit the local server
        print("Adding ipykernel from local mirror...")
        result = subprocess.run(
            ["uv", "add", "ipykernel", "--no-cache"],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            pytest.fail("Failed to add package from local mirror")

        assert "ipykernel" in (project_dir / "pyproject.toml").read_text()
        print("Successfully added ipykernel from local mirror!")

    finally:
        server_proc.terminate()
        server_proc.wait()
