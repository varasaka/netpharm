# netpharm.spec — PyInstaller build recipe for the desktop launcher.
#
# Build (run ON the OS you want the binary for):
#     pyinstaller packaging/netpharm.spec --noconfirm
#
# Produces dist/NetworkPharmacology/  (a folder containing the launcher
# executable + everything it needs). Ship that whole folder; the user runs the
# executable inside it. See packaging/README_PACKAGING.md.
#
# Note: this freezes the self-contained parts (Streamlit UI, RDKit, STRING/
# Enrichr/PubChem HTTP agents, intersection, hub genes, reporting). Playwright
# (Agents 3-4) and Cytoscape (Agent 9) remain external by nature and are used
# only if present at runtime — the app degrades gracefully without them.

from PyInstaller.utils.hooks import collect_all, copy_metadata
import os

# SPECPATH is injected by PyInstaller = directory containing this spec (packaging/).
PROJECT_ROOT = os.path.dirname(SPECPATH)  # noqa: F821 - SPECPATH provided by PyInstaller


def P(*parts):
    return os.path.join(PROJECT_ROOT, *parts)


datas, binaries, hiddenimports = [], [], []

# Heavy packages that need their data files + metadata collected wholesale.
for pkg in [
    "streamlit",
    "rdkit",
    "networkx",
    "altair",       # streamlit dependency
    "pyarrow",      # streamlit dependency
]:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:  # noqa: BLE001
        print(f"[spec] collect_all({pkg}) skipped: {exc}")

# Streamlit reads its own version metadata at runtime.
try:
    datas += copy_metadata("streamlit")
except Exception:
    pass

# Our own source tree + default config, placed so desktop_launcher._resource_root
# finds them at <root>/src/... and <root>/config/config.yaml.
datas += [
    (P("src", "netpharm"), os.path.join("src", "netpharm")),
    (P("config", "config.yaml"), "config"),
    (P("README.md"), "."),
]

# Modules imported lazily inside agents (PyInstaller can't see these statically).
hiddenimports += [
    "langgraph", "langgraph.graph",
    "anthropic",
    "docx",            # python-docx
    "reportlab", "reportlab.lib", "reportlab.platypus",
    "markdown",
    "yaml",
    "pandas", "requests",
    "netpharm", "netpharm.agents", "netpharm.orchestrator",
]

block_cipher = None

a = Analysis(
    [P("packaging", "desktop_launcher.py")],
    pathex=[P("src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NetworkPharmacology",
    console=True,           # keep a console so users can see progress/errors
    icon=None,              # drop an .ico path here to brand the exe
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="NetworkPharmacology",
)
