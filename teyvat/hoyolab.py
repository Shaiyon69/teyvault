"""HoYoLAB / HoYoverse HTTP calls. Global (os_*) servers only."""
import base64
import hashlib
import http.cookies
import json
import random
import secrets
import ssl
import string
import time
import urllib.parse
import urllib.request
import uuid

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

CHECKIN_URL = "https://sg-hk4e-api.hoyolab.com/event/sol/sign?lang=en-us"
CHECKIN_ACT_ID = "e202102251931481"
CHECKIN_HOME_URL = "https://sg-hk4e-api.hoyolab.com/event/sol/home"
CHECKIN_INFO_URL = "https://sg-hk4e-api.hoyolab.com/event/sol/info"
ROLES_URL = "https://api-account-os.hoyolab.com/account/binding/api/getUserGameRolesByCookie"
RECORD_URL = "https://bbs-api-os.hoyolab.com/game_record/genshin/api/index"
CHARACTERS_URL = "https://bbs-api-os.hoyolab.com/game_record/genshin/api/character/list"
CHARACTER_DETAIL_URL = "https://bbs-api-os.hoyolab.com/game_record/genshin/api/character/detail"
DAILY_NOTE_URL = "https://bbs-api-os.hoyolab.com/game_record/genshin/api/dailyNote"
# Battle Chronicle wants the "DS" header the hoyolab.com web page signs its requests with.
DS_SALT = "6s25p5ox5y14umn1p61aqyyvbvvl3lrt"
REDEEM_URL = "https://sg-hk4e-api.hoyoverse.com/common/apicdkey/api/webExchangeCdkeyHyl"
# Email/password login, the call account.hoyolab.com makes. Used where no login window exists (phones).
LOGIN_URL = "https://sg-public-api.hoyolab.com/account/ma-passport/api/webLoginByPassword"
LOGIN_HEADERS = {"x-rpc-app_id": "c9oqaq3s3gu8", "x-rpc-client_type": "4",
                 "Origin": "https://account.hoyolab.com", "Referer": "https://account.hoyolab.com/"}
# RSA public key (2048-bit SubjectPublicKeyInfo) the login page encrypts the account and password with.
LOGIN_KEY = ("MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA4PMS2JVMwBsOIrYWRluYwEiFZL7Aphtm9z5Eu/anzJ09nB00uhW+"
             "ScrDWFECPwpQto/GlOJYCUwVM/raQpAj/xvcjK5tNVzzK94mhk+j9RiQ+aWHaTXmOgurhxSp3YbwlRDvOgcq5yPiTz0+kSeK"
             "ZJcGeJ95bvJ+hJ/UMP0Zx2qB5PElZmiKvfiNqVUk8A8oxLJdBB5eCpqWV6CUqDKQKSQP4sM0mZvQ1Sr4UcACVcYgYnCbTZMW"
             "hJTWkrNXqI8TMomekgny3y+d6NX/cFa66jozFIF4HCX5aW8bp8C8vq2tFvFbleQ/Q3CU56EWWKMrOcpmFtRmC18s9biZBVR/"
             "8QIDAQAB")
RETCODE_CAPTCHA = -3101
DEVICE_ID = str(uuid.uuid4())  # one per run, so a captcha retry comes from the same "device"

# Built apps (flet build, Android, iOS) ship no system CA bundle, so every HTTPS call would fail
# with CERTIFICATE_VERIFY_FAILED; certifi comes with flet (via httpx).
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = None
SIGN_HEADERS = {"x-rpc-signgame": "hk4e"}  # the check-in page sends it on every event/sol call

RETCODE_ALREADY_SIGNED = -5003
REDEEM_COOLDOWN_S = 6


class ApiError(Exception):
    def __init__(self, retcode, message):
        super().__init__(f"{message} (retcode {retcode})")
        self.retcode = retcode


def request(url, *, cookies=None, params=None, body=None, referer=None, headers=None) -> dict:
    """Send a request, return the parsed JSON envelope. Raises ApiError on non-zero retcode."""
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    headers = {"User-Agent": UA, "Accept": "application/json", **(headers or {})}
    if cookies:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    if referer:
        headers["Referer"] = referer
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=20, context=SSL_CONTEXT) as resp:
        payload = json.load(resp)
    if payload.get("retcode") != 0:
        raise ApiError(payload.get("retcode"), payload.get("message", "unknown error"))
    return payload


def rsa_encrypt(text) -> str:
    """PKCS#1 v1.5 encryption with LOGIN_KEY, base64, like the login page (stdlib, no crypto package)."""
    der = base64.b64decode(LOGIN_KEY)
    n = int.from_bytes(der[33:289], "big")  # modulus; the key ends with exponent 65537
    msg = text.encode()
    pad = bytes(secrets.randbelow(255) + 1 for _ in range(256 - 3 - len(msg)))  # non-zero random bytes
    m = int.from_bytes(b"\x00\x02" + pad + b"\x00" + msg, "big")
    return base64.b64encode(pow(m, 65537, n).to_bytes(256, "big")).decode()


class CaptchaRequired(ApiError):
    """HoYoLAB wants a Geetest v3 captcha first. `gt`/`challenge` start it; pass the solved
    getValidate() dict to login() as `captcha`."""
    def __init__(self, aigis):
        super().__init__(RETCODE_CAPTCHA, "HoYoLAB asked for a captcha")
        self.session_id = aigis["session_id"]
        self.gt, self.challenge = (json.loads(aigis["data"])[k] for k in ("gt", "challenge"))


def login(account, password, captcha=None) -> dict:
    """Sign in with a HoYoLAB email/username and password. Returns the login cookies from Set-Cookie.
    The password goes only to HoYoLAB (RSA-encrypted) and is never stored. Raises CaptchaRequired
    when HoYoLAB wants a captcha; call again with captcha=(CaptchaRequired, solved getValidate() dict)."""
    body = {"account": rsa_encrypt(account.strip()), "password": rsa_encrypt(password), "token_type": 6}
    headers = {"User-Agent": UA, "Content-Type": "application/json", "x-rpc-device_id": DEVICE_ID, **LOGIN_HEADERS}
    if captcha:
        need, solved = captcha
        headers["x-rpc-aigis"] = f"{need.session_id};{base64.b64encode(json.dumps(solved).encode()).decode()}"
    req = urllib.request.Request(LOGIN_URL, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=20, context=SSL_CONTEXT) as resp:
        payload = json.load(resp)
        jar = http.cookies.SimpleCookie()
        for header in resp.headers.get_all("Set-Cookie") or []:
            jar.load(header)
        aigis = resp.headers.get("x-rpc-aigis")
    if payload.get("retcode") == RETCODE_CAPTCHA and aigis:
        raise CaptchaRequired(json.loads(aigis))
    if payload.get("retcode") != 0:
        raise ApiError(payload.get("retcode"), payload.get("message", "unknown error"))
    return {k: m.value for k, m in jar.items()}


def checkin(cookies) -> str:
    """Claim today's daily reward. Returns a human-readable status."""
    try:
        request(CHECKIN_URL, cookies=cookies, body={"act_id": CHECKIN_ACT_ID},
                referer="https://act.hoyolab.com/", headers=SIGN_HEADERS)
    except ApiError as e:
        if e.retcode == RETCODE_ALREADY_SIGNED:
            return "Already checked in today."
        raise
    return "Checked in."


def checkin_month(cookies) -> dict:
    """This month's reward calendar (same calls the check-in web page makes). The calendar is public,
    so it still comes back when the signed-in progress call fails; `error` then says why."""
    params = {"lang": "en-us", "act_id": CHECKIN_ACT_ID}
    awards = request(CHECKIN_HOME_URL, params=params, headers=SIGN_HEADERS)["data"]["awards"]
    try:
        info = request(CHECKIN_INFO_URL, cookies=cookies, params=params,
                       referer="https://act.hoyolab.com/", headers=SIGN_HEADERS)["data"]
    except Exception as ex:
        return {"awards": awards, "signed": 0, "today_done": False, "error": str(ex)}
    return {"awards": awards, "signed": info["total_sign_day"], "today_done": info["is_sign"], "error": None}


def game_roles(cookies) -> list[dict]:
    payload = request(ROLES_URL, cookies=cookies, params={"game_biz": "hk4e_global"})
    return payload["data"]["list"]


def ds_header() -> str:
    t, r = int(time.time()), "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{t},{r},{hashlib.md5(f'salt={DS_SALT}&t={t}&r={r}'.encode()).hexdigest()}"


def _record(url, cookies, role, body=None) -> dict:
    """Battle Chronicle call, signed and headed like the hoyolab.com page sends it. Read-only."""
    params = None if body else {"server": role["region"], "role_id": role["game_uid"]}
    if body:
        body = {"server": role["region"], "role_id": role["game_uid"], **body}
    return request(url, cookies=cookies, referer="https://act.hoyolab.com/", params=params, body=body,
                   headers={"DS": ds_header(), "x-rpc-app_version": "1.5.0",
                            "x-rpc-client_type": "5", "x-rpc-language": "en-us"})["data"]


def game_record(cookies, role) -> dict:
    """Battle Chronicle summary: stats, world exploration per region, teapot."""
    return _record(RECORD_URL, cookies, role)


def daily_note(cookies, role) -> dict:
    """Real-time notes: resin, commissions, realm currency, expeditions. Fails until the player turns
    on "Real-time Notes" in the Battle Chronicle settings."""
    return _record(DAILY_NOTE_URL, cookies, role)


def characters(cookies, role) -> list[dict]:
    """Owned characters: level, constellation, friendship, equipped weapon."""
    return _record(CHARACTERS_URL, cookies, role, {"sort_type": 1})["list"]


def character_detail(cookies, role, character_id) -> tuple[dict, dict]:
    """One character's build (weapon, artifacts, stats, talents, constellations), plus the
    property_map that names the numeric property_type ids. One id per call, like the web page."""
    data = _record(CHARACTER_DETAIL_URL, cookies, role, {"character_ids": [character_id]})
    return data["list"][0], data["property_map"]


def redeem(cookies, codes, *, uid=None, sleep=time.sleep) -> list[tuple[str, str]]:
    """Redeem codes on one account. Returns [(code, result message)]."""
    roles = game_roles(cookies)
    if not roles:
        raise SystemExit("No Genshin account bound to this HoYoLAB login.")
    role = next((r for r in roles if r["game_uid"] == uid), None) if uid else roles[0]
    if role is None:
        raise SystemExit(f"UID {uid} not found on this HoYoLAB login.")
    results = []
    for i, code in enumerate(codes):
        if i:
            sleep(REDEEM_COOLDOWN_S)
        try:
            request(REDEEM_URL, cookies=cookies, referer="https://genshin.hoyoverse.com/", params={
                "cdkey": code.strip().upper(), "game_biz": "hk4e_global", "lang": "en",
                "region": role["region"], "uid": role["game_uid"], "t": int(time.time() * 1000),
            })
            results.append((code, "redeemed"))
        except ApiError as e:
            results.append((code, str(e)))
    return results
