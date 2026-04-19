# ray: Agent Instructions

This document provides foundational mandates and procedural guidance for AI agents working on the **ray** project.

## Core Principles

- **Cross-Platform Integrity:** All changes must respect both Linux and Windows environments. Never assume a POSIX-only or Windows-only architecture.
- **Performance First:** Building mirrors is I/O intensive. Favor parallel execution (e.g., `ThreadPoolExecutor`) for network operations.
- **Dependency Strictness:** Prioritize binary wheel resolution (`--only-binary=:all:`) and explicit platform/version tagging during downloads.
- **Minimal Footprint:** Use temporary files for intermediate processes to keep the user workspace clean.

## Procedural Mandates

### 1. Tooling
- Always use `uv` for environment management, dependency addition, and running scripts.
- Use `ruff` for all linting and formatting. A task is not complete until `uv run ruff check . --fix && uv run ruff format .` has been executed.
- Use `pytest` for verification. New features must be accompanied by an end-to-end test in `tests/`.

### 2. The Mirror Workflow
- **Compilation:** Must iterate through all supported `pyvers` and `target_platforms`.
- **Download:** Must use a comprehensive list of `manylinux` tags to ensure glibc compatibility across different package release standards.
- **Indexing:** Always run `simple503 --sort` after downloads to maintain a PEP 503 compliant structure.

### 3. Verification
- Before submitting any changes to `process_reqs.py`, run `tests/test_mirror_flow.py` to ensure `ipykernel` (our benchmark for complex dependency trees) can still be served and installed correctly.

## Personality & Tone
- Be direct, technical, and concise. 
- Prioritize high-signal output. 
- Focus on the "why" of architectural decisions (e.g., why a specific glibc version is required).
