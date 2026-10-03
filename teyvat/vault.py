"""HoYoLAB cookie storage. Desktop: OS keyring. Android/iOS (no keyring backend): a file in the
app's private sandbox, which other apps cannot read. Cookies never go into SQLite."""
import json
import os
from pathlib import Path

try:
    import keyring
    from keyring.errors import KeyringError
except ImportError:
    keyring = None
    KeyringError = Exception

SERVICE = "teyvault"
LEGACY_SERVICES = ("teylogs", "teyvat-auditor")  # earlier app names; moved to SERVICE on first load
KEY = "hoyolab-cookies"

# Only these are kept; everything else in a pasted browser cookie string is dropped.
WANTED = ("ltoken_v2", "ltuid_v2", "ltmid_v2", "cookie_token_v2", "account_id_v2", "account_mid_v2")


class NotLoggedIn(Exception):
    pass


def parse_cookie_string(raw: str) -> dict:
    pairs = (p.strip().split("=", 1) for p in raw.split(";") if "=" in p)
    return {k: v for k, v in pairs if k in WANTED and v}


def _sandbox_file() -> Path:
    # NOTE: plain file in the mobile app sandbox, protected by OS app isolation and device
    # encryption, not by Keychain/Keystore. Swap for a secure-storage plugin if Flet ships one.
    app_dir = os.environ.get("FLET_APP_STORAGE_DATA")
    if not app_dir:
        raise RuntimeError("No OS keyring available and not running as a packaged app.")
    return Path(app_dir) / "cookies.json"


def _keyring(op, *args):
    """Run a keyring op; returns (ok, result). ok=False means no usable backend (mobile)."""
    if keyring is None:
        return False, None
    try:
        return True, getattr(keyring, op)(SERVICE, KEY, *args)
    except KeyringError as e:
        if type(e).__name__ == "NoKeyringError":
            return False, None
        raise


def save(cookies: dict) -> None:
    ok, _ = _keyring("set_password", json.dumps(cookies))
    if not ok:
        _sandbox_file().write_text(json.dumps(cookies))


def load() -> dict:
    ok, raw = _keyring("get_password")
    for legacy in LEGACY_SERVICES if ok and not raw else ():
        if raw := keyring.get_password(legacy, KEY):
            keyring.set_password(SERVICE, KEY, raw)
            keyring.delete_password(legacy, KEY)
            break
    if not ok and _sandbox_file().exists():
        raw = _sandbox_file().read_text()
    if not raw:
        raise NotLoggedIn("No HoYoLAB cookies stored. Log in first.")
    return json.loads(raw)


def delete() -> None:
    try:
        ok, _ = _keyring("delete_password")
    except KeyringError:  # nothing stored
        ok = True
    if not ok:
        _sandbox_file().unlink(missing_ok=True)
