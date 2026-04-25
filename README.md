# ray: your local bit of uv

[![Test Matrix](https://github.com/josephcbradley/ray/actions/workflows/test.yml/badge.svg)](https://github.com/josephcbradley/ray/actions/workflows/test.yml) [![Coverage](https://codecov.io/gh/josephcbradley/ray/branch/main/graph/badge.svg)](https://codecov.io/gh/josephcbradley/ray)

**ray** is an automated system for building and hosting a local PyPI mirror. It is designed to support firewalled environments or offline CI/CD pipelines by pre-compiling requirement files across multiple Python versions and platforms (Linux, Windows, and macOS).

---

## 1. Setting up Requirements

1.  **Define Core Dependencies:** Edit `reqs/core.in` for packages required by all environments.
2.  **Define Feature Dependencies:** Add other `.in` files to `reqs/` (e.g., `ai.in`, `data.in`).
3.  **Platform Detection:** The system automatically detects your host platform and targets it.

## 2. Managing the Mirror (CLI)

Use `process_reqs.py` to synchronize, compile, download, or index your mirror.

### **Quick Start (Sync Everything)**
The `sync` command is the most common entry point. It compiles all `.in` files, downloads missing wheels, and rebuilds the PEP 503 index:

```bash
uv run python process_reqs.py sync
```

### **Granular Subcommands**

| Command | Description |
| :--- | :--- |
| `sync` | (Default) Runs compile, download, and index in sequence. |
| `compile` | Only generates pinned `.out` files from your `.in` requirements. |
| `download` | Downloads wheels from all `.out` files into the `simple/` directory. |
| `index` | Only rebuilds the PEP 503 HTML structure using `simple503`. |

### **Customizing the Build**
You can override default directories and targeted Python versions:

```bash
uv run python process_reqs.py sync \
  --reqs-dir my_reqs \
  --outputs-dir build_pins \
  --simple-dir my_pypi \
  --pyvers 3.12 3.13
```

---

## 3. Serving the Mirror

Host the `simple/` directory using any static file server (e.g., Nginx, Apache, or Python's built-in server):

```bash
# Example using Python's http.server (port 8080)
cd simple && python -m http.server 8080
```

---

## 4. Developer Setup

When initializing a new project, use the provided wrapper scripts to pre-configure `uv` to use your local mirror.

### **Linux/macOS**
```bash
./ray.sh my-new-project
```

### **Windows (PowerShell)**
```powershell
.\ray.ps1 my-new-project
```

**This configuration:**
- Sets the default index to `http://localhost:8080/simple/`.
- Pre-configures `uv` to resolve for the current platform environment.

---

## Troubleshooting

- **Large Binaries:** If you accidentally commit a wheel (`.whl`), remove it using `git rm --cached <file>`. The `.gitignore` now blocks these by default.
- **Missing Wheels:** Check `error_log.txt` if a download fails. This usually happens if a specific version doesn't have a binary wheel for your target platform/ABI.
- **Logs:** Logs are written to `error_log.txt` with detailed stderr from `uv` and `pip`.
