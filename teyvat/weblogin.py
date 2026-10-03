"""Desktop sign-in through the real hoyolab.com login page, shown in a pywebview window. Once the
login cookies appear (HttpOnly ones included) the window closes and they are printed as JSON.
pywebview must own the main thread, which Flet already does, so the GUI runs this as a subprocess."""
import json
import subprocess
import sys
import time

from teyvat import vault

URL = "https://www.hoyolab.com/"
TIMEOUT_S = 600


def sign_in() -> dict:
    """Opens the login window and blocks until the user logs in or closes it. Returns cookies."""
    # NOTE: assumes sys.executable is a Python interpreter (pip install / dev run). A frozen
    # `flet build windows` exe would need main.py to dispatch a --weblogin flag instead.
    proc = subprocess.run([sys.executable, "-m", "teyvat.weblogin"], capture_output=True, text=True,
                          timeout=TIMEOUT_S, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    lines = proc.stdout.strip().splitlines()
    cookies = json.loads(lines[-1]) if lines else {}
    if "ltoken_v2" not in cookies:
        raise RuntimeError("Sign-in window closed before login finished."
                           + (f"\n{proc.stderr.strip()[-300:]}" if proc.returncode else ""))
    return cookies


def _main():
    import webview

    found = {}

    def watch(window):
        while not found:
            time.sleep(1)
            try:
                jar = window.get_cookies()
            except Exception:  # window closed by the user
                return
            cookies = {k: m.value for c in jar for k, m in c.items() if k in vault.WANTED}
            if "ltoken_v2" in cookies and "ltuid_v2" in cookies:
                found.update(cookies)
                window.destroy()

    window = webview.create_window("Log in to HoYoLAB (closes when done)", URL, width=1000, height=760)
    webview.start(watch, window)  # private mode: fresh session every time, nothing left on disk
    print(json.dumps(found))


if __name__ == "__main__":
    _main()
