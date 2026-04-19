import argparse
import subprocess
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Download Python binaries for offline use via uv."
    )
    parser.add_argument(
        "--dir", required=True, help="Directory to store Python installations"
    )
    parser.add_argument(
        "versions",
        nargs="*",
        default=["3.12", "3.13", "3.14"],
        help="Python versions to download",
    )
    args = parser.parse_args()

    target_dir = Path(args.dir).absolute()
    target_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["UV_PYTHON_INSTALL_DIR"] = str(target_dir)

    print(
        f"Downloading Python versions {', '.join(args.versions)} into {target_dir}..."
    )

    cmd = ["uv", "python", "install"] + args.versions
    result = subprocess.run(cmd, env=env)

    if result.returncode == 0:
        print("\nSuccessfully cached Python versions!")
        print(
            "To use these offline, set the UV_PYTHON_INSTALL_DIR environment variable:"
        )
        print(f'  Linux/macOS: export UV_PYTHON_INSTALL_DIR="{target_dir}"')
        print(f'  Windows (PowerShell): $env:UV_PYTHON_INSTALL_DIR="{target_dir}"')
    else:
        print("Failed to download Python versions.", file=sys.stderr)
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
