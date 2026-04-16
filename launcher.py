"""
E2Open Duty Cockpit — launcher
-----------------------------------------------------------
Build the portable .exe bundle with:   build_exe.bat
Distribute the entire dist/DutyCockpit/ folder.
End-users double-click DutyCockpit.exe — no Python needed.
-----------------------------------------------------------
Architecture:
  - Main process  → Tkinter status window
  - Worker process → the same .exe respawned with env var
                     _DUTYCOCKPIT_WORKER=1; runs Streamlit
    (subprocess instead of multiprocessing avoids frozen-app
     multiprocessing quirks that break Streamlit's async server)
-----------------------------------------------------------
"""
import os
import socket
import subprocess
import sys
import time
import threading
import webbrowser

_WORKER_ENV = "_DUTYCOCKPIT_WORKER"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bundle_dir() -> str:
    if getattr(sys, "frozen", False):
        return sys._MEIPASS          # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))


def _exe_dir() -> str:
    """Directory that contains DutyCockpit.exe (parent of _internal)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Worker mode  —  runs Streamlit, no GUI
# ---------------------------------------------------------------------------

def _run_as_worker() -> None:
    bundle_dir = _bundle_dir()
    app_py     = os.path.join(bundle_dir, "app.py")

    os.chdir(bundle_dir)
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)

    # os.chdir(bundle_dir) is critical: Streamlit reads .streamlit/config.toml
    # relative to cwd at startup.  The config.toml bundled alongside the exe sets
    # headless=true and developmentMode=false, which prevents the 404 caused by
    # Streamlit trying to proxy the frontend JS to a Node dev server on port 3000.
    import streamlit as _st
    # Belt-and-suspenders for older Streamlit builds where _RELEASE still matters.
    try:
        _st._RELEASE = True
    except AttributeError:
        pass

    from streamlit.web import bootstrap  # noqa: PLC0415
    bootstrap.run(app_py, False, [], {})


# ---------------------------------------------------------------------------
# Main — Tkinter status window
# ---------------------------------------------------------------------------

def main() -> None:
    import tkinter as tk
    from tkinter import messagebox

    PORT      = 8501
    APP_TITLE = "E2Open Duty Cockpit"
    APP_URL   = f"http://localhost:{PORT}"
    PURPLE    = "#A100FF"
    DARK_PRP  = "#460073"
    WHITE     = "#FFFFFF"

    bundle = _bundle_dir()
    app_py = os.path.join(bundle, "app.py")

    if not os.path.exists(app_py):
        messagebox.showerror(
            APP_TITLE,
            f"app.py not found in:\n{bundle}\n\n"
            "Make sure DutyCockpit.exe is inside the DutyCockpit folder.",
        )
        return

    # ── Spawn worker subprocess ───────────────────────────────────────────
    log_path = os.path.join(_exe_dir(), "streamlit_worker.log")
    env = os.environ.copy()
    env[_WORKER_ENV] = "1"
    # Pre-populate Streamlit config so the worker subprocess inherits them
    # before Python (and thus Streamlit) even starts.
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    env["STREAMLIT_SERVER_PORT"] = str(PORT)
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
    env["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"

    log_file = open(log_path, "w", encoding="utf-8")   # stdout+stderr → log
    # When running from source (unfrozen) we must pass the script path explicitly;
    # when frozen, sys.executable IS the bundle entry-point so no extra arg is needed.
    cmd = [sys.executable]
    if not getattr(sys, "frozen", False):
        cmd.append(os.path.abspath(__file__))
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=log_file,
        stderr=log_file,
    )

    # Open browser only after the Streamlit port is actually reachable
    def _open_browser():
        for _ in range(30):          # wait up to 30 seconds
            time.sleep(1)
            try:
                with socket.create_connection(("localhost", PORT), timeout=1):
                    break
            except OSError:
                continue
        webbrowser.open(APP_URL)

    threading.Thread(target=_open_browser, daemon=True).start()

    # ── Tkinter status window ─────────────────────────────────────────────
    win = tk.Tk()
    win.title(APP_TITLE)
    win.geometry("360x170")
    win.resizable(False, False)
    win.configure(bg=WHITE)

    tk.Frame(win, bg=DARK_PRP, height=5).pack(fill="x")

    tk.Label(
        win,
        text=APP_TITLE,
        font=("Segoe UI", 13, "bold"),
        bg=WHITE,
        fg=DARK_PRP,
        pady=14,
    ).pack()

    status_lbl = tk.Label(
        win,
        text="⏳  Starting server…",
        font=("Segoe UI", 9),
        bg=WHITE,
        fg="#888",
    )
    status_lbl.pack()

    btn_frame = tk.Frame(win, bg=WHITE, pady=16)
    btn_frame.pack()

    tk.Button(
        btn_frame,
        text="Open Browser",
        command=lambda: webbrowser.open(APP_URL),
        bg=PURPLE,
        fg=WHITE,
        font=("Segoe UI", 9, "bold"),
        relief="flat",
        padx=14,
        pady=6,
        cursor="hand2",
    ).pack(side="left", padx=8)

    def _stop():
        proc.terminate()
        log_file.close()
        win.destroy()

    tk.Button(
        btn_frame,
        text="Stop & Close",
        command=_stop,
        bg="#e8e8e8",
        fg="#333",
        font=("Segoe UI", 9),
        relief="flat",
        padx=14,
        pady=6,
        cursor="hand2",
    ).pack(side="left", padx=8)

    def _on_close():
        if messagebox.askokcancel("Quit", "Stop the application and close?"):
            _stop()

    win.protocol("WM_DELETE_WINDOW", _on_close)

    _marked_ready = [False]

    def _poll():
        if proc.poll() is not None:          # worker process has exited
            log_tail = ""
            try:
                log_file.flush()
                with open(log_path, encoding="utf-8") as f:
                    log_tail = f"\n\nLog:\n{f.read()[-800:]}"
            except Exception:
                pass
            messagebox.showerror(
                APP_TITLE,
                f"Streamlit server stopped unexpectedly.{log_tail}",
            )
            win.destroy()
            return
        if not _marked_ready[0]:
            # Only mark ready once the port actually responds
            try:
                with socket.create_connection(("localhost", PORT), timeout=0.5):
                    _marked_ready[0] = True
                    status_lbl.config(
                        text=f"●  Running  —  {APP_URL}",
                        fg="#1a7a40",
                    )
            except OSError:
                pass
        win.after(2000, _poll)

    win.after(5000, _poll)
    win.mainloop()

    if proc.poll() is None:
        proc.terminate()
    if not log_file.closed:
        log_file.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()   # no-op unless started by multiprocessing

    if os.environ.get(_WORKER_ENV):
        _run_as_worker()
    else:
        main()
