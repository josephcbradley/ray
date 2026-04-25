import argparse
from pathlib import Path
import subprocess
import logging
import sys
import tempfile
import shutil
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    filename="error_log.txt",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def log_error(context: str, details: str):
    """Logs an error to the file and prints a notification to stderr."""
    msg = f"{context}\nDetails: {details}\n"
    logging.error(msg)
    print(f"ERROR: {context}. See error_log.txt for details.", file=sys.stderr)


def run_cmd(cmd: list[str], context: str, capture_output: bool = False):
    """Runs a subprocess command and logs any errors."""
    try:
        result = subprocess.run(
            cmd, capture_output=capture_output, text=True if capture_output else False
        )
        if result.returncode != 0:
            err_msg = (
                result.stderr
                if capture_output and result.stderr
                else f"Command exited with code {result.returncode}"
            )
            log_error(context, err_msg)
        return result.returncode == 0
    except Exception as e:
        log_error(context, str(e))
        return False


def get_current_platform():
    """Detects the current platform and returns a normalized name."""
    if sys.platform == "win32":
        return "windows"
    elif sys.platform == "darwin":
        return "macos"
    else:
        return "linux"


def compile_reqs(reqs_to_process, core_req, outputs_dir, pyvers, target_platforms):
    """Compiles requirement files into .out files."""
    for pyver in pyvers:
        for target_platform in target_platforms:
            for req in reqs_to_process:
                output_file = outputs_dir / f"{req.stem}_{target_platform}_{pyver}.out"
                print(f"Compiling {req.name} for {pyver} on {target_platform}")
                cmd = [
                    "uv",
                    "pip",
                    "compile",
                    str(core_req),
                    str(req),
                    "--python-platform",
                    target_platform,
                    "--python-version",
                    pyver,
                    "-o",
                    str(output_file),
                ]
                run_cmd(
                    cmd,
                    f"Compilation failed for {req.name} ({pyver}, {target_platform})",
                    capture_output=True,
                )


def download_task(pyver, target_platform, out_file, simple_dir):
    """Worker task for parallel downloads from a specific .out file."""
    print(f"Downloading packages for {pyver} on {target_platform} from {out_file.name}")

    if target_platform == "linux":
        platforms = [
            "manylinux_2_34_x86_64",
            "manylinux_2_28_x86_64",
            "manylinux_2_17_x86_64",
            "manylinux_2_12_x86_64",
        ]
    elif target_platform == "windows":
        platforms = ["win_amd64"]
    elif target_platform == "macos":
        platforms = ["macosx_10_12_x86_64", "macosx_11_0_arm64"]
    else:
        platforms = []

    with tempfile.TemporaryDirectory() as temp_down_dir:
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "pip",
            "download",
            "-r",
            str(out_file),
            "-d",
            temp_down_dir,
            "--no-deps",
            "--python-version",
            pyver,
            "--only-binary=:all:",
        ]
        if platforms:
            for p in platforms:
                cmd.extend(["--platform", p])

        success = run_cmd(
            cmd,
            f"Download failed for {out_file.name} ({pyver}, {target_platform})",
            capture_output=True,
        )

        if success:
            for item in Path(temp_down_dir).iterdir():
                dest_file = simple_dir / item.name
                if not dest_file.exists():
                    shutil.move(str(item), str(dest_file))
        return success


def download_reqs(outputs_dir, simple_dir, pyvers, target_platforms):
    """Downloads wheels for all compiled .out files."""
    tasks = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        for pyver in pyvers:
            for target_platform in target_platforms:
                for out_file in outputs_dir.glob(f"*_{target_platform}_{pyver}.out"):
                    tasks.append(
                        executor.submit(
                            download_task,
                            pyver,
                            target_platform,
                            out_file,
                            simple_dir,
                        )
                    )
        for task in tasks:
            task.result()


def index_reqs(simple_dir):
    """Generates the PEP 503 index."""
    print("Generating PEP 503 index with simple503")
    cmd_simple503 = [
        "uvx",
        "simple503",
        "--sort",
        str(simple_dir),
    ]
    run_cmd(cmd_simple503, "Failed to generate simple503 index", capture_output=False)


def main():
    parser = argparse.ArgumentParser(description="ray: local PyPI mirror manager")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # Common options
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--reqs-dir", default="reqs", help="Input .in files directory")
    parent_parser.add_argument("--outputs-dir", default="outputs", help="Compiled .out files directory")
    parent_parser.add_argument("--simple-dir", default="simple", help="Target PEP 503 directory")
    parent_parser.add_argument("--pyvers", nargs="+", default=["3.12", "3.13", "3.14"], help="Python versions to target")

    # Sync (Default)
    sync_parser = subparsers.add_parser("sync", parents=[parent_parser], help="Compile, download, and index")

    # Compile
    compile_parser = subparsers.add_parser("compile", parents=[parent_parser], help="Only compile requirement files")

    # Download
    download_parser = subparsers.add_parser("download", parents=[parent_parser], help="Only download wheels from compiled files")

    # Index
    index_parser = subparsers.add_parser("index", parents=[parent_parser], help="Only rebuild the PEP 503 index")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    reqs_path = Path(args.reqs_dir)
    outputs_dir = Path(args.outputs_dir)
    simple_dir = Path(args.simple_dir)
    pyvers = args.pyvers

    outputs_dir.mkdir(exist_ok=True)
    simple_dir.mkdir(exist_ok=True)

    target_platforms = [get_current_platform()]

    reqs_to_process = []
    if reqs_path.exists():
        for path in reqs_path.rglob("*.in"):
            if path.stem != "core":
                reqs_to_process.append(path)

    core_req = reqs_path / "core.in"

    if args.command == "compile":
        if not core_req.exists():
            log_error("Compile failed", "core.in not found")
            return
        compile_reqs(reqs_to_process, core_req, outputs_dir, pyvers, target_platforms)

    elif args.command == "download":
        download_reqs(outputs_dir, simple_dir, pyvers, target_platforms)

    elif args.command == "index":
        index_reqs(simple_dir)

    elif args.command == "sync":
        if not core_req.exists():
            log_error("Sync failed", "core.in not found")
            return
            
        # Compile if needed
        for req in reqs_to_process:
            output_file = outputs_dir / f"{req.stem}_{target_platforms[0]}_{pyvers[0]}.out"
            # If any target out file doesn't exist, we run compile for all
            if not output_file.exists():
                 print(f"--- Processing {req.name} ---")
                 compile_reqs([req], core_req, outputs_dir, pyvers, target_platforms)
        
        # Always download
        download_reqs(outputs_dir, simple_dir, pyvers, target_platforms)
        index_reqs(simple_dir)


if __name__ == "__main__":
    main()
