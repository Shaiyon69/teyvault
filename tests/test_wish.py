import unittest
from unittest import mock

from teyvat import db, vault, wish

STANDARD = {"Diluc": "2020-09-28", "Tighnari": "2022-09-28"}


def pull(i, name="Debate Club", rank=3, gacha_type="301", time="2024-01-01 00:00:00"):
    return {"id": str(1000 + i), "uid": "600000001", "gacha_type": gacha_type,
            "item_type": "Character" if rank == 5 else "Weapon", "name": name, "rank": rank,
            "time": time}


class TestAuthkey(unittest.TestCase):
    def test_extract_last_gacha_url(self):
        blob = (b"\x00junk https://example.com/other?authkey=nope\x00"
                b"1/0/https://gs.hoyoverse.com/genshin/event/e20190909gacha-v3/index.html?"
                b"authkey_ver=1&authkey=OLD&game_biz=hk4e_global\x00\x00"
                b"https://gs.hoyoverse.com/genshin/event/e20190909gacha-v3/index.html?"
                b"authkey_ver=1&authkey=NEW%2Bkey&game_biz=hk4e_global#/log\x00")
        url = wish.extract_gacha_url(blob)
        self.assertIn("authkey=NEW%2Bkey", url)
        endpoint, params = wish.api_params(url)
        self.assertEqual(params["authkey"], "NEW+key")
        self.assertIn("hoyoverse.com/gacha_info", endpoint)

    def test_game_dir_from_log(self):
        log = ("[Subsystems] Discovering subsystems at path "
               "C:/Program Files/HoYoPlay/games/Genshin Impact game/GenshinImpact_Data/UnitySubsystems\n")
        self.assertEqual(wish.find_game_data_dir(log).as_posix(),
                         "C:/Program Files/HoYoPlay/games/Genshin Impact game/GenshinImpact_Data")


class TestStats(unittest.TestCase):
    def test_pity_and_5050(self):
        rows = ([pull(i) for i in range(73)] + [pull(73, "Diluc", 5)]          # lost at 74
                + [pull(74 + i) for i in range(9)] + [pull(83, "Furina", 5)]   # guaranteed at 10
                + [pull(84, "Tighnari", 5, time="2022-08-25 12:00:00")]        # pre-standard: won
                + [pull(85 + i, gacha_type="400") for i in range(3)])          # shared pity
        s = wish.stats(rows, STANDARD)["character"]
        self.assertEqual([f["pity"] for f in s["five_stars"]], [74, 10, 1])
        self.assertEqual([f["outcome"] for f in s["five_stars"]], ["lost", "guaranteed", "won"])
        self.assertEqual((s["won"], s["lost"], s["pity"], s["guaranteed"]), (1, 1, 3, False))

    def test_weapon_pool_has_no_5050(self):
        s = wish.stats([pull(0, "Wolf's Gravestone", 5, "302")], STANDARD)["weapon"]
        self.assertIsNone(s["five_stars"][0]["outcome"])
        self.assertEqual(s["hard_pity"], 80)

    def test_four_star_pity(self):
        rows = [pull(0), pull(1, rank=4), pull(2), pull(3, "Diluc", 5), pull(4)]
        s = wish.stats(rows, STANDARD)["character"]
        self.assertEqual((len(s["four_stars"]), s["pity4"]), (1, 3))  # a 5★ does not reset 4★ pity
        self.assertEqual(s["four_stars"][0]["pity"], 2)

    def test_icon_url_matches_paimon_file_names(self):
        self.assertTrue(wish.icon_url("Hu Tao", "Character").endswith("/characters/hu_tao.png"))
        self.assertTrue(wish.icon_url("Wolf's Gravestone", "Weapon").endswith("/weapons/wolfs_gravestone.png"))
        self.assertTrue(wish.icon_url("Freedom-Sworn", "Weapon").endswith("/weapons/freedom-sworn.png"))
        self.assertTrue(wish.icon_url('"The Catch"', "Weapon").endswith("/weapons/the_catch.png"))


class TestStorage(unittest.TestCase):
    def test_uigf_round_trip_and_idempotent_insert(self):
        src = db.connect(":memory:")
        rows = [pull(i) for i in range(5)] + [pull(5, gacha_type="400")]
        self.assertEqual(db.insert_wishes(src, rows), 6)
        self.assertEqual(db.insert_wishes(src, rows), 0)
        data = wish.export_uigf(src)
        self.assertEqual(data["hk4e"][0]["list"][-1]["uigf_gacha_type"], "301")
        dst = db.connect(":memory:")
        self.assertEqual(wish.import_uigf(dst, data), 6)
        self.assertEqual(db.wishes(dst, "600000001"), db.wishes(src, "600000001"))

    def test_xlsx_round_trip(self):
        src = db.connect(":memory:")
        rows = [pull(i) for i in range(5)] + [pull(5, "Diluc", 5, "200")]
        rows[0]["id"] = "1700000000000000001"  # 19 digits: must survive Excel as text
        db.insert_wishes(src, rows)
        dst = db.connect(":memory:")
        self.assertEqual(wish.import_xlsx(dst, wish.export_xlsx(src)), 6)
        self.assertEqual(db.wishes(dst, "600000001"), db.wishes(src, "600000001"))

    def test_paimon_xlsx_import_and_sync_overlap(self):
        from io import BytesIO
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Character Event"
        ws.append(("Type", "Name", "Time", "⭐", "Pity", "#Roll", "Group", "Banner", "Part"))
        for roll in range(1, 11):  # one 10-pull, same second; roll keeps the order
            ws.append(("Weapon", f"W{roll}", "2024-01-01 00:00:00", 3, 1, roll, 1, "x", ""))
        ws.append(("Character", "Diluc", "2024-03-01 00:00:00", 5, 11, 11, 2, "x", ""))
        buf = BytesIO()
        wb.save(buf)
        conn = db.connect(":memory:")
        with self.assertRaises(SystemExit):  # no UID anywhere
            wish.import_xlsx(conn, buf.getvalue())
        self.assertEqual(wish.import_xlsx(conn, buf.getvalue(), "600000001"), 11)
        self.assertEqual(wish.import_xlsx(conn, buf.getvalue(), "600000001"), 0)  # stable ids
        self.assertEqual([r["name"] for r in db.wishes(conn, "600000001")][:3], ["W1", "W2", "W3"])
        # A later sync brings the 5★ back with a real id: the synthetic copy goes away.
        real = {**pull(0, "Diluc", 5, time="2024-03-01 00:00:00"), "id": "1709251200000000001"}
        db.insert_wishes(conn, [real])
        self.assertEqual(db.drop_covered_synthetic(conn), 1)
        names = [r["name"] for r in db.wishes(conn, "600000001")]
        self.assertEqual((len(names), names[-1]), (11, "Diluc"))

    def test_fetch_stops_at_known_id(self):
        api_items = [{**pull(i), "rank_type": "3"} for i in range(30, 0, -1)]  # newest first
        pages = [api_items[:20], api_items[20:]]
        calls = []

        def fake_request(endpoint, params):
            calls.append(params["end_id"])
            return {"data": {"list": pages[len(calls) - 1]}}

        with mock.patch.object(wish, "request", fake_request):
            rows = wish.fetch_type("e", {}, "301", lambda i: i == "1005",
                                   sleep=lambda s: None, log=lambda m: None)
        self.assertEqual(len(rows), 25)  # ids 1030..1006
        self.assertEqual(calls, ["0", "1011"])


class TestVault(unittest.TestCase):
    def test_parse_cookie_string_keeps_only_wanted(self):
        raw = "_ga=x; ltoken_v2=abc; ltuid_v2=123; mi18nLang=en-us; cookie_token_v2=t=1"
        self.assertEqual(vault.parse_cookie_string(raw),
                         {"ltoken_v2": "abc", "ltuid_v2": "123", "cookie_token_v2": "t=1"})


if __name__ == "__main__":
    unittest.main()
