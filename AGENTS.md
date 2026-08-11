# AGENTS.md

## Cursor Cloud specific instructions

`pyd-decompiler` is a **single, offline Python CLI tool** (no web server, API, database, or long-running services). It analyzes/decompiles Windows `.pyd` PE modules. "Running the app" means invoking the CLI; there is nothing to keep running in the background.

### Environment notes (non-obvious)
- Use `python3`, not `python` — the VM has no `python` alias on PATH.
- The update script (`pip install -e .`) installs into the user site; the console entry point lands in `~/.local/bin`, which is **not on PATH**. Prefer running the module form `python3 -m pyd_decompiler ...` (or call `~/.local/bin/pyd-decompiler` directly).
- The VM runs Python 3.12. The `decompyle3`/`uncompyle6` backends only support bytecode up to Python 3.8, so for modern (3.9+) embedded bytecode the tool automatically falls back to the stdlib `dis` disassembler. This is expected, not a bug.
- The optional `pycdc` binary is not installed; that backend is skipped gracefully.

### Commands (standard; see README.md / pyproject.toml)
- Lint / syntax check: `python3 -m compileall -q pyd_decompiler tests`
- Tests: `python3 -m unittest discover -s tests -v`
- Run: `python3 -m pyd_decompiler <file.pyd> -o <outdir>` (see `README.md` for `--scan-only`, `--no-decompile`, `--backend`).

### End-to-end testing
- The repo ships **no sample `.pyd`**. To exercise the full analyze → scan → extract → decompile pipeline, generate a minimal PE that embeds a real `.pyc` blob (a valid PE is required, since `analyze_pyd` errors out on non-PE input before scanning). The unit tests, by contrast, synthesize `.pyc` bytes in-memory and need no fixtures.
