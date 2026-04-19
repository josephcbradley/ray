from pathlib import Path
import subprocess
import logging
import sys

# Configure logging
logging.basicConfig(
    filename="error_log.txt",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def log_error(context: str, details: str):
    """Logs an error to the file and prints a notification to stderr."""
    msg = f"{context}\nDetails: {details}\n"
    logging.error(msg)
    print(f"ERROR: {context}. See error_log.txt for details.", file=sys.stderr)

def run_cmd(cmd: list[str], context: str, capture_output: bool = False):
    """Runs a subprocess command and logs any errors."""
    try:
        result = subprocess.run(cmd, capture_output=capture_output, text=True if capture_output else False)
        if result.returncode != 0:
            err_msg = result.stderr if capture_output and result.stderr else f"Command exited with code {result.returncode}"
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

def main():
    try:
        # 1. Setup paths
        reqs_path = Path("reqs")
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
                    output_file = outputs_dir / f"{req.stem}_{target_platform}_{pyver}.out"
                    print(f"Compiling {req} for {pyver} on {target_platform}")
                    cmd = [
                        "uv", "pip", "compile", 
                        str(core_req), str(req), 
                        "--python-platform", target_platform, 
                        "--python-version", pyver, 
                        "-o", str(output_file)
                    ]
                    # We capture output here so compilation logs stay quiet unless there's an error
                    run_cmd(cmd, f"Compilation failed for {req} ({pyver}, {target_platform})", capture_output=True)

        # 4. Consolidate into all_pkgs.txt
        combined_str = []
        for reqpath in outputs_dir.iterdir():
            if reqpath.suffix == ".out":
                with open(reqpath, "r") as infile: 
                    lines = infile.readlines()
                    combined_str.extend(lines)
                    
        print(f"Initial lines gathered: {len(combined_str)}")
        # Deduplicate and filter out comments/empty lines
        combined_str = list(set([line for line in combined_str if line.strip() and nohash(line)]))
        print(f"Unique packages: {len(combined_str)}")
        
        all_pkgs_path = "all_pkgs.txt"
        with open(all_pkgs_path, "w") as outfile:
            outfile.write("".join(combined_str))

        # 5. Download version-specific wheels
        for pyver in pyvers:
            for target_platform in target_platforms:
                print(f"Downloading for {pyver} on {target_platform}")
                
                # Map simple platform names to tags pip recognizes
                if target_platform == "linux":
                    # We provide multiple manylinux tags because pip download is strict with --platform
                    # and won't automatically resolve the hierarchy (e.g. 2_34 matches 2_34, but 2_28 needs 2_28).
                    platforms = ["manylinux_2_34_x86_64", "manylinux_2_28_x86_64", "manylinux_2_17_x86_64", "manylinux_2_12_x86_64"]
                else:
                    platforms = ["win_amd64"]

                cmd = [
                    "uv", "run", "python", "-m", "pip", "download", 
                    "-r", all_pkgs_path, 
                    "-d", str(simple_dir), 
                    "--no-deps", 
                    "--python-version", pyver, 
                    "--only-binary=:all:"
                ]
                for p in platforms:
                    cmd.extend(["--platform", p])

                # We don't capture output for downloads so the progress bar is still visible
                run_cmd(cmd, f"Download failed for {pyver} on {target_platform}", capture_output=False)

        # 6. Generate PEP 503 index
        print("Generating PEP 503 index with simple503")
        cmd_simple503 = ["uv", "run", "simple503", "--sort", str(simple_dir)]
        run_cmd(cmd_simple503, "Failed to generate simple503 index", capture_output=False)

    except Exception as e:
        log_error("Unexpected error in main execution", str(e))

if __name__ == "__main__":
    main()