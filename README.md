# pyd-decompiler

Analyze and decompile **Python `.pyd` extension modules** (Windows PE DLLs).

`.pyd` files are compiled native extensions — usually C, C++, **Cython**, or **Nuitka** — not plain Python bytecode. This tool:

1. **Analyzes** the PE structure (exports, imports, sections, strings)
2. **Detects** module type (CPython extension, Cython, Nuitka, pybind11)
3. **Scans** for embedded `.pyc` bytecode blobs inside the binary
4. **Decompiles** extracted bytecode to `.py` when possible

> **Important:** Most `.pyd` files cannot be fully recovered as Python source. Native code requires reverse-engineering tools (Ghidra, IDA). This tool helps when bytecode is embedded (some packers/protectors) and provides useful metadata for RE.

## Install

```bash
pip install -e .
# or
pip install -r requirements.txt
```

Optional: install [pycdc](https://github.com/zrax/pycdc) for better decompilation of Python 3.9+ bytecode.

## Usage

```bash
# Full analysis + bytecode scan + decompile
python -m pyd_decompiler module.pyd

# Custom output directory
python -m pyd_decompiler module.pyd -o output/

# PE analysis only (no bytecode extraction)
python -m pyd_decompiler module.pyd --scan-only

# Extract .pyc without decompiling
python -m pyd_decompiler module.pyd --no-decompile

# Prefer a specific decompiler backend
python -m pyd_decompiler module.pyd --backend pycdc
```

## Output structure

```
module_decompiled/
├── analysis_report.txt      # Human-readable PE analysis
├── analysis_report.json     # Machine-readable report
├── extracted_pyc/           # Embedded bytecode (if found)
│   └── module_000_py311.pyc
└── decompiled_source/       # Recovered Python source (if decompilable)
    └── module_000_py311.py
```

## Decompiler backends (tried in order)

| Backend     | Python versions | Notes                          |
|------------|-----------------|--------------------------------|
| decompyle3 | 3.7–3.8         | Best for older bytecode        |
| uncompyle6 | 2.7–3.8         | Legacy support                 |
| pycdc      | 2.7–3.12+       | External binary, broad support |
| dis        | any             | Bytecode disassembly fallback  |

## Limitations

- **Cython / Nuitka / C extensions:** Machine code only — no Python source recovery
- **Embedded bytecode:** Only recovered if present in the binary
- **Obfuscation:** May block decompilation even when bytecode exists

## License

MIT
