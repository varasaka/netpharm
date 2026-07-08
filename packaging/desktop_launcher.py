"""Desktop launcher.

Turns the Streamlit UI into a double-click desktop app: it starts the Streamlit
server on a free local port, waits until it answers, opens the default browser
at that address, and keeps running until the window/terminal is closed.

This is what PyInstaller freezes into the native executable (see netpharm.spec).
It works the same whether run from source (`python packaging/desktop_launcher.py`)
or as the frozen binary.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _resource_root() -> Path:
    """Read-only assets root (bundled code + default config).

    Under PyInstaller these are unpacked to sys._MEIPASS (a temp dir); from
    source it is the project root.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def _work_dir() -> Path:
    """Writable directory for config edits, the SQLite DB, and outputs.

    Frozen: a folder next to the executable, so results persist and the
    read-only bundle is never written to. From source: the project root.
    """
    if getattr(sys, "frozen", False):
        wd = Path(sys.executable).resolve().parent / "netpharm_workspace"
    else:
        wd = Path(__file__).resolve().parents[1]
    wd.mkdir(parents=True, exist_ok=True)
    return wd


def _ensure_workspace(resource_root: Path, work_dir: Path) -> None:
    """Seed the work dir with a config the user can edit, plus outputs/."""
    import shutil

    cfg_dst = work_dir / "config" / "config.yaml"
    if not cfg_dst.exists():
        cfg_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resource_root / "config" / "config.yaml", cfg_dst)
    (work_dir / "outputs").mkdir(exist_ok=True)


def _free_port(preferred: int = 8501) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def _open_browser_when_ready(port: int) -> None:
    url = f"http://127.0.0.1:{port}"
    for _ in range(60):  # up to ~30s
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.5)
    webbrowser.open(url)


def main() -> None:
    resource_root = _resource_root()
    work_dir = _work_dir()
    _ensure_workspace(resource_root, work_dir)

    app_path = str(resource_root / "src" / "netpharm" / "ui" / "streamlit_app.py")

    # Import the bundled netpharm code from the read-only root, but run from the
    # writable work dir so config/config.yaml and outputs/ resolve there.
    sys.path.insert(0, str(resource_root / "src"))
    os.chdir(work_dir)

    port = _free_port()
    threading.Thread(target=_open_browser_when_ready, args=(port,), daemon=True).start()

    # Configure and launch Streamlit in-process (works inside a frozen binary).
    from streamlit import config as st_config
    from streamlit.web import bootstrap

    st_config.set_option("server.headless", True)
    st_config.set_option("server.port", port)
    st_config.set_option("browser.gatherUsageStats", False)
    st_config.set_option("global.developmentMode", False)

    print(f"Network Pharmacology Platform starting at http://127.0.0.1:{port}")
    print("Close this window to stop the app.")

    # bootstrap.run signature: (main_script_path, is_hello, args, flag_options)
    try:
        bootstrap.run(app_path, False, [], {})
    except TypeError:
        # Older/newer Streamlit variants use a slightly different signature.
        bootstrap.run(app_path, "", [], {})


if __name__ == "__main__":
    main()
