# Project TODOs

- [x] Update `get_current_platform()` in `process_reqs.py` to use `platform.system().lower()` (Option 1) instead of `sys.platform` checks, preventing Pylance from statically pruning platform branches as unreachable dead code.
