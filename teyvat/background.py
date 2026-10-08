"""Work that runs without the window: Windows Task Scheduler starts `teyvault daily --notify` every hour,
which checks in, redeems new promo codes and sends real-time note alerts. The GUI uses the same helpers."""
import datetime
import os
import subprocess
import sys
from pathlib import Path

from teyvat import db, hoyolab, vault

TASK = "Teyvault"
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW: no console flashing up every hour
# NOTE: toasts are sent as Windows PowerShell (its AppUserModelID), so they say "Windows PowerShell";
# register our own AppUserModelID with a Start-menu shortcut if the name matters.
TOAST_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"


def setting(conn, key) -> bool:
    """On/off settings that default to on: auto_checkin, auto_redeem, alerts."""
    return db.get_meta(conn, key, "1") == "1"


def task_command() -> list[str]:
    """How the scheduled task starts Teyvault: the installed exe, or this Python without a console."""
    if getattr(sys, "frozen", False):  # flet pack build; main.py handles --daily
        return [sys.executable, "--daily"]
    pyw = Path(sys.executable).with_name("pythonw.exe")
    return [str(pyw if pyw.exists() else sys.executable), "-m", "teyvat.cli", "daily", "--notify"]


def _schtasks(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["schtasks", *args], capture_output=True, text=True, creationflags=NO_WINDOW)


def scheduled() -> bool:
    return os.name == "nt" and _schtasks("/Query", "/TN", TASK).returncode == 0


def schedule(on: bool) -> None:
    """Add or remove the hourly task. Hourly, not daily, so a PC that was off at the set time still
    checks in; runs that find nothing to do make no check-in request.
    NOTE: schtasks' defaults skip runs on battery; create it from XML if laptops need it."""
    if on:
        cmd = subprocess.list2cmdline(task_command())
        r = _schtasks("/Create", "/F", "/SC", "HOURLY", "/TN", TASK, "/TR", cmd)
    else:
        r = _schtasks("/Delete", "/F", "/TN", TASK)
    if r.returncode and (on or scheduled()):
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())


def notify(title, body) -> None:
    """Windows toast notification (WinRT through Windows PowerShell, no extra package). No-op elsewhere."""
    if os.name != "nt":
        return
    q = lambda s: s.replace("'", "''")
    ps = ("$m=[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime];"
          "$x=$m::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
          "$t=$x.GetElementsByTagName('text');"
          f"[void]$t.Item(0).AppendChild($x.CreateTextNode('{q(title)}'));"
          f"[void]$t.Item(1).AppendChild($x.CreateTextNode('{q(body)}'));"
          f"$m::CreateToastNotifier('{TOAST_APP_ID}').Show([Windows.UI.Notifications.ToastNotification]::new($x))")
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                   creationflags=NO_WINDOW)


def new_alerts(conn, uid, note) -> list[str]:
    """Alerts of a daily_note that weren't active last time (the GUI and the hourly task share the DB,
    so each alert shows once). A condition that clears can alert again later."""
    now = hoyolab.note_alerts(note)
    before = set(db.get_json(conn, f"alerts:{uid}", []))
    db.set_json(conn, f"alerts:{uid}", sorted(now))
    return [msg for key, msg in now.items() if key not in before]


def auto_redeem(conn, cookies, uid) -> list[tuple[str, str]]:
    """Redeem the live codes this account hasn't tried yet. Every code the server answered for is
    remembered (redeemed, already used, expired), so each is sent once."""
    # NOTE: a code HoYoLAB rejects for its rate limit (-2016) is remembered too; the 6 s spacing avoids it.
    if "cookie_token_v2" not in cookies:
        return []
    done = set(db.get_json(conn, f"codes_done:{uid}", []))
    todo = [c for c in hoyolab.active_codes() if c not in done]
    if not todo:
        return []
    results = hoyolab.redeem(cookies, todo, uid=uid)
    db.set_json(conn, f"codes_done:{uid}", sorted(done | {c for c, _ in results}))
    return results


def active_uid(conn, roles) -> str | None:
    """The account picked in Settings (default_uid), else the first."""
    uid = db.get_meta(conn, "default_uid")
    return next((r["game_uid"] for r in roles if r["game_uid"] == uid), roles[0]["game_uid"] if roles else None)


def run_daily(conn) -> tuple[list[str], list[str]]:
    """One background pass: check-in (once a day), new codes, note alerts. Returns (news, errors);
    a failing step doesn't stop the others."""
    cookies = vault.load()
    news, errors = [], []
    today = datetime.date.today().isoformat()
    if setting(conn, "auto_checkin") and db.get_meta(conn, "last_checkin") != today:
        try:
            news.append(f"Daily check-in: {hoyolab.checkin(cookies)}")
            db.set_meta(conn, "last_checkin", today)
        except Exception as e:
            errors.append(f"Check-in failed: {e}")
    try:
        roles = hoyolab.game_roles(cookies)
    except Exception as e:
        return news, errors + [f"Could not load game accounts: {e}"]
    uid = active_uid(conn, roles)
    if not uid:
        return news, errors
    if setting(conn, "auto_redeem"):
        try:
            got = [c for c, r in auto_redeem(conn, cookies, uid) if r == "redeemed"]
            if got:
                news.append(f"Redeemed {len(got)} new code(s): {', '.join(got)}. Rewards are in your in-game mail.")
        except Exception as e:
            errors.append(f"Code redeem failed: {e}")
    if setting(conn, "alerts"):
        try:
            role = next(r for r in roles if r["game_uid"] == uid)
            news += new_alerts(conn, uid, hoyolab.daily_note(cookies, role))
        except Exception as e:
            errors.append(f"Real-time notes failed: {e}")
    return news, errors
