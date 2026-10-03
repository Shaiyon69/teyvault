import argparse
import getpass
import json
import sys

from teyvat import db, hoyolab, vault, wish


def cmd_login(args):
    raw = getpass.getpass("Paste HoYoLAB cookie string (input hidden): ")
    cookies = vault.parse_cookie_string(raw)
    missing = [k for k in ("ltoken_v2", "ltuid_v2") if k not in cookies]
    if missing:
        sys.exit(f"Cookie string is missing {', '.join(missing)}.")
    if "cookie_token_v2" not in cookies:
        print("Note: no cookie_token_v2, so `redeem` will not work. Check-in still will.")
    vault.save(cookies)
    print(f"Stored {len(cookies)} cookies in the OS keyring.")


def cmd_logout(args):
    vault.delete()
    print("Cookies removed from the OS keyring.")


def cmd_checkin(args):
    print(hoyolab.checkin(vault.load()))


def cmd_redeem(args):
    for code, result in hoyolab.redeem(vault.load(), args.codes, uid=args.uid):
        print(f"{code}: {result}")


def cmd_wish_sync(args):
    url = args.url or wish.locate_gacha_url(args.user_dir)
    with db.connect() as conn:
        print(f"Added {wish.sync(conn, url)} new wishes.")


def cmd_wish_stats(args):
    standard = wish.load_standard()
    conn = db.connect()
    uids = [args.uid] if args.uid else db.uids(conn)
    if not uids:
        sys.exit("No wishes stored. Run `teyvat wish sync` first.")
    for uid in uids:
        print(f"UID {uid}")
        for pool, s in wish.stats(db.wishes(conn, uid), standard).items():
            line = f"  {pool:<10} {s['total']:>5} pulls  pity {s['pity']}/{s['hard_pity']}"
            if pool == "character":
                line += f"  50/50 won {s['won']} lost {s['lost']}"
                line += "  (next 5* guaranteed)" if s["guaranteed"] else ""
            print(line)
            for f in s["five_stars"][-args.last:]:
                tag = f" [{f['outcome']}]" if f["outcome"] else ""
                print(f"      {f['time'][:10]}  {f['name']} @ {f['pity']}{tag}")


def cmd_wish_export(args):
    if args.file.lower().endswith(".xlsx"):
        with db.connect() as conn, open(args.file, "wb") as fh:
            fh.write(wish.export_xlsx(conn))
        print(f"Exported to {args.file}.")
        return
    with open(args.file, "w", encoding="utf-8") as fh:
        json.dump(wish.export_uigf(db.connect()), fh, ensure_ascii=False, indent=1)
    print(f"Exported to {args.file}.")


def cmd_wish_import(args):
    if args.file.lower().endswith(".xlsx"):
        with db.connect() as conn, open(args.file, "rb") as fh:
            print(f"Imported {wish.import_xlsx(conn, fh.read(), args.uid)} new wishes.")
        return
    with open(args.file, encoding="utf-8") as fh:
        data = json.load(fh)
    with db.connect() as conn:
        print(f"Imported {wish.import_uigf(conn, data)} new wishes.")


def main(argv=None):
    p = argparse.ArgumentParser(prog="teyvault", description="Genshin Impact account companion.")
    sub = p.add_subparsers(required=True)

    sub.add_parser("login", help="store HoYoLAB cookies in the OS keyring").set_defaults(fn=cmd_login)
    sub.add_parser("logout", help="remove stored cookies").set_defaults(fn=cmd_logout)
    sub.add_parser("checkin", help="claim the HoYoLAB daily reward").set_defaults(fn=cmd_checkin)

    r = sub.add_parser("redeem", help="redeem promo codes")
    r.add_argument("codes", nargs="+")
    r.add_argument("--uid", help="game UID (default: first account on the login)")
    r.set_defaults(fn=cmd_redeem)

    w = sub.add_parser("wish", help="wish history").add_subparsers(required=True)
    s = w.add_parser("sync", help="fetch new wishes from the game API")
    s.add_argument("--url", help="wish history URL (skips cache lookup)")
    s.add_argument("--user-dir", help="Windows user dir, e.g. inside a Wine prefix")
    s.set_defaults(fn=cmd_wish_sync)
    st = w.add_parser("stats", help="pity and 50/50 summary")
    st.add_argument("--uid")
    st.add_argument("--last", type=int, default=5, help="5-stars to list per banner")
    st.set_defaults(fn=cmd_wish_stats)
    e = w.add_parser("export", help="export UIGF v4 JSON, or Excel if FILE ends in .xlsx")
    e.add_argument("file")
    e.set_defaults(fn=cmd_wish_export)
    i = w.add_parser("import", help="import UIGF JSON (v2-v4), or a Teyvault / paimon.moe .xlsx")
    i.add_argument("file")
    i.add_argument("--uid", help="account for paimon.moe files, which have no UID (default: the only UID in the DB)")
    i.set_defaults(fn=cmd_wish_import)

    args = p.parse_args(argv)
    try:
        args.fn(args)
    except hoyolab.ApiError as e:
        sys.exit(f"API error: {e}")
    except vault.NotLoggedIn as e:
        sys.exit(f"{e} Run `teyvat login`.")


if __name__ == "__main__":
    main()
