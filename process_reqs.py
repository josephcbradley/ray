from pathlib import Path
import subprocess
import logging
import sys
import tempfile
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


def nohash(text: str) -> bool:
    if "#" in text:
        return False
    else:
        return True


def download_task(pyver, target_platform, all_pkgs_path, simple_dir):
    """Worker task for parallel downloads."""
    print(f"Downloading for {pyver} on {target_platform}")

    # Map simple platform names to tags pip recognizes
    if target_platform == "linux":
        platforms = [
            "manylinux_2_34_x86_64",
            "manylinux_2_28_x86_64",
            "manylinux_2_17_x86_64",
            "manylinux_2_12_x86_64",
        ]
    else:
        platforms = ["win_amd64"]

    cmd = [
        "uv",
        "run",
        "python",
        "-m",
        "pip",
        "download",
        "-r",
        str(all_pkgs_path),
        "-d",
        str(simple_dir),
        "--no-deps",
        "--python-version",
        pyver,
        "--only-binary=:all:",
    ]
    for p in platforms:
        cmd.extend(["--platform", p])

    return run_cmd(
        cmd, f"Download failed for {pyver} on {target_platform}", capture_output=True
    )


def main(reqs_path_str: str = "reqs"):
    try:
        # 1. Setup paths
        reqs_path = Path(reqs_path_str)
        outputs_dir = Path("outputs")
        outputs_dir.mkdir(exist_ok=True)
        simple_dir = Path("simple")
        simple_dir.mkdir(exist_ok=True)

        # 2. Identify requirement files
        reqs_to_process: list[Path] = []
        for path in reqs_path.rglob("*.in"):
            if path.stem == "core":
                continue
            reqs_to_process.append(path)

        core_req = reqs_path / Path("core.in")
        if not core_req.is_file():
            raise FileNotFoundError("Could not find the core file.")

        # 3. Compile for all versions and platforms
        pyvers = ["3.12", "3.13", "3.14"]
        target_platforms = ["linux", "windows"]

        for pyver in pyvers:
            for target_platform in target_platforms:
                for req in reqs_to_process:
                    output_file = (
                        outputs_dir / f"{req.stem}_{target_platform}_{pyver}.out"
                    )
                    print(f"Compiling {req} for {pyver} on {target_platform}")
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
                        f"Compilation failed for {req} ({pyver}, {target_platform})",
                        capture_output=True,
                    )

        # 4. Consolidate into a temporary requirement file
        combined_str = []
        for reqpath in outputs_dir.iterdir():
            if reqpath.suffix == ".out":
                with open(reqpath, "r") as infile:
                    lines = infile.readlines()
                    combined_str.extend(lines)

        print(f"Initial lines gathered: {len(combined_str)}")
        # Deduplicate and filter out comments/empty lines
        combined_str = list(
            set([line for line in combined_str if line.strip() and nohash(line)])
        )
        print(f"Unique packages: {len(combined_str)}")

        # Security/Cleanliness: Use a temporary file for the combined package list
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tf:
            tf.write("".join(combined_str))
            all_pkgs_path = Path(tf.name)

        try:
            # 5. Download version-specific wheels in parallel
            tasks = []
            with ThreadPoolExecutor(max_workers=4) as executor:
                for pyver in pyvers:
                    for target_platform in target_platforms:
                        tasks.append(
                            executor.submit(
                                download_task,
                                pyver,
                                target_platform,
                                all_pkgs_path,
                                simple_dir,
                            )
                        )

                # Wait for all tasks to complete
                for task in tasks:
                    task.result()

        finally:
            # Clean up the temporary requirement file
            if all_pkgs_path.exists():
                all_pkgs_path.unlink()

        # 6. Generate PEP 503 index
        print("Generating PEP 503 index with simple503")
        cmd_simple503 = ["uv", "run", "simple503", "--sort", str(simple_dir)]
        run_cmd(
            cmd_simple503, "Failed to generate simple503 index", capture_output=False
        )

    except Exception as e:
        log_error("Unexpected error in main execution", str(e))


if __name__ == "__main__":
    main()
