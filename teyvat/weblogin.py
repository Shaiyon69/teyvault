"""Desktop sign-in through the real hoyolab.com login page, shown in a pywebview window. Once the
login cookies appear (HttpOnly ones included) the window closes and they are printed as JSON.
pywebview must own the main thread, which Flet already does, so the GUI runs this as a subprocess."""
import json
import subprocess
import sys
import tempfile
import threading
import time

from teyvat import vault

URL = "https://www.hoyolab.com/"
TIMEOUT_S = 600


def sign_in() -> dict:
    """Opens the login window and blocks until the user logs in or closes it. Returns cookies."""
    # The installed app (`flet pack`, PyInstaller) re-launches itself; main.py routes --weblogin here.
    cmd = [sys.executable, "--weblogin"] if getattr(sys, "frozen", False) else [sys.executable, "-m", "teyvat.weblogin"]
    # Read the one JSON line, not until EOF: WebView2's helper processes inherit stdout and
    # can outlive the window, so EOF may never come. The child enforces TIMEOUT_S itself.
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err, text=True,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        line = next((l for l in proc.stdout if l.startswith("{")), "")  # skip any library chatter
        proc.wait()
        err.seek(0)
        stderr = err.read().decode(errors="replace").strip()
    cookies = json.loads(line) if line else {}
    if "ltoken_v2" not in cookies:
        raise RuntimeError("Sign-in window closed before login finished."
                           + (f"\n{stderr[-300:]}" if proc.returncode else ""))
    return cookies


def show(title, url):
    """A plain pywebview window on `url` (the wiki's interactive maps). Fire and forget."""
    cmd = [sys.executable, "--weblogin"] if getattr(sys, "frozen", False) else [sys.executable, "-m", "teyvat.weblogin"]
    subprocess.Popen(cmd + ["--show", title, url], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _main():
    import webview

    if "--show" in sys.argv:
        title, url = sys.argv[sys.argv.index("--show") + 1:][:2]
        webview.create_window(title, url, width=1200, height=800)
        return webview.start()

    found = {}
    closed = threading.Event()

    def watch(window):
        deadline = time.monotonic() + TIMEOUT_S
        while not found and not closed.wait(1):  # closed by the user
            if time.monotonic() > deadline:
                window.destroy()
                return
            try:
                jar = window.get_cookies()
            except Exception:
                return
            cookies = {k: m.value for c in jar or [] for k, m in c.items() if k in vault.WANTED}
            if "ltoken_v2" in cookies and "ltuid_v2" in cookies:
                found.update(cookies)
                window.destroy()

    window = webview.create_window("Log in to HoYoLAB (closes when done)", URL, width=1000, height=760)
    window.events.closed += closed.set
    try:
        webview.start(watch, window)  # private mode: fresh session every time, nothing left on disk
    finally:  # always answer, or sign_in() waits on a pipe the WebView2 helpers keep open
        print(json.dumps(found), flush=True)


if __name__ == "__main__":
    _main()
