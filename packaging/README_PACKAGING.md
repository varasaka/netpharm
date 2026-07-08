# Packaging the platform as a desktop app

This turns the project into a **double-click application** that opens in the
browser, so end users never touch Python or the command line.

## Read this first: the honest constraints

- **Executables are OS-specific.** A Windows `.exe` runs only on Windows; macOS
  and Linux need their own binaries. There is no single file that runs on all
  three, and you cannot build a Windows `.exe` on a Mac (or vice-versa). Run the
  matching build script **on each OS** you want to support.
- **Two features stay external by nature** and are used only if present:
  - **Cytoscape** (Agent 9 styling / PNG / SVG / `.cys`) is a separate desktop
    program. The app talks to it over `http://127.0.0.1:1234`. Without it, the
    app still exports GraphML networks.
  - **Playwright's Chromium** (Agents 3–4, SwissADME / SwissTargetPrediction) is
    a ~150 MB browser installed once with `playwright install chromium`. Without
    it, those two agents use their labelled demo data; everything else is real.

Everything else — the Streamlit UI, RDKit standardization, STRING PPI, Enrichr
enrichment, PubChem lookups, intersection, hub genes, and the DOCX/PDF/MD/HTML
report — is fully bundled inside the app.

## Build it (one command, on the target OS)

You need Python 3.10–3.12 installed. From the project root:

| OS | Command |
|----|---------|
| Windows | `packaging\build_windows.bat` |
| macOS | `bash packaging/build_macos.sh` |
| Linux | `bash packaging/build_linux.sh` |

Each script creates an isolated build environment, installs the requirements,
and runs PyInstaller. It takes a few minutes and produces:

```
dist/NetworkPharmacology/          ← ship this whole folder
   NetworkPharmacology(.exe)       ← the app users double-click
   _internal/ ...                  ← bundled Python, RDKit, Streamlit, code
```

The folder is self-contained (~600 MB, mostly RDKit + Streamlit). Zip it and
share it; the recipient just unzips and runs the executable — no Python needed.

## What the user sees

Double-clicking the executable:
1. starts the app on a free local port,
2. opens their default browser at it,
3. creates a **`netpharm_workspace/`** folder next to the executable containing
   an editable `config/config.yaml` and all `outputs/` (CSVs, networks, report).

Closing the console window stops the app.

## Distributing to non-technical users

- **Windows:** zip `dist/NetworkPharmacology/` and send it. Users unzip and run
  `NetworkPharmacology.exe`. (Windows SmartScreen may warn on first run for an
  unsigned app — "More info → Run anyway", or code-sign the exe for production.)
- **macOS:** the binary is unsigned, so Gatekeeper blocks it until you either
  right-click → Open once, or sign + notarize it with an Apple Developer ID.
- **Optional installers:** to get a real `Setup.exe` / `.dmg` with a shortcut,
  wrap `dist/NetworkPharmacology/` with **Inno Setup** (Windows) or
  **create-dmg** (macOS). Those wrap the folder this build already produces.

## Enabling the external agents on a user's machine

- Cytoscape features: install Cytoscape ≥3.9 with stringApp / cytoHubba / MCODE,
  and leave it open before running a live analysis.
- ADME / target agents: run `playwright install chromium` once. The build
  scripts print the exact command for the build environment; for a shipped app,
  run it in a terminal on the target machine.

## Single-file variant

The spec builds a folder (`--onedir`), which is the reliable choice for
Streamlit + RDKit. A single `--onefile` exe is possible but unzips ~600 MB to a
temp dir on every launch (slow) and more often trips antivirus. Stick with the
folder unless you have a specific reason not to.
