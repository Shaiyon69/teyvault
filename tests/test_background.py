import datetime
import unittest
from unittest import mock

from teyvat import background, db, hoyolab, wiki

NOTE = {"current_resin": 185, "max_resin": 200, "current_home_coin": 2400, "max_home_coin": 2400,
        "expeditions": [{"status": "Finished"}, {"status": "Finished"}],
        "transformer": {"obtained": True, "recovery_time": {"reached": False}}}
UTC = datetime.timezone.utc


class TestAlerts(unittest.TestCase):
    def test_note_alerts(self):
        self.assertEqual(set(hoyolab.note_alerts(NOTE)), {"resin", "expeditions", "home_coin"})
        calm = {**NOTE, "current_resin": 20, "current_home_coin": 0, "expeditions": [{"status": "Ongoing"}]}
        self.assertEqual(hoyolab.note_alerts(calm), {})

    def test_each_alert_once_until_it_clears(self):
        conn = db.connect(":memory:")
        self.assertEqual(len(background.new_alerts(conn, "1", NOTE)), 3)
        self.assertEqual(background.new_alerts(conn, "1", NOTE), [])
        background.new_alerts(conn, "1", {**NOTE, "current_resin": 0})
        self.assertEqual(len(background.new_alerts(conn, "1", NOTE)), 1)  # resin filled up again


class TestAutoRedeem(unittest.TestCase):
    def test_only_untried_codes_are_sent(self):
        conn = db.connect(":memory:")
        cookies = {"cookie_token_v2": "x"}
        redeem = lambda c, codes, uid: [(code, "redeemed") for code in codes]
        with mock.patch.object(hoyolab, "active_codes", return_value=["A", "B"]), \
                mock.patch.object(hoyolab, "redeem", side_effect=redeem) as sent:
            self.assertEqual(len(background.auto_redeem(conn, cookies, "1")), 2)
            self.assertEqual(background.auto_redeem(conn, cookies, "1"), [])
            self.assertEqual(sent.call_count, 1)
            self.assertEqual(background.auto_redeem(conn, {}, "2"), [])  # no cookie_token_v2


class TestTimes(unittest.TestCase):
    def test_next_resets(self):
        now = datetime.datetime(2026, 10, 8, 19, 0, tzinfo=UTC)  # Fri 03:00 in UTC+8
        daily, weekly = wiki.next_resets("os_asia", now)
        self.assertEqual((daily.day, daily.hour), (9, 4))
        self.assertEqual((weekly.day, weekly.weekday()), (12, 0))

    def test_reruns(self):
        b = lambda ids, s, e: {"featured": ids, "start": s, "end": e}
        data = {"characters": [b(["venti"], "2020-09-28 00:00:00", "2020-10-18 00:00:00"),
                               b(["venti"], "2021-03-17 00:00:00", "2021-04-06 00:00:00"),
                               b(["klee"], "2020-10-20 00:00:00", "2020-11-10 00:00:00"),
                               b(["zhongli"], "2021-12-01 00:00:00", "2021-12-31 00:00:00"),
                               b(["xiao"], "2022-01-01 00:00:00", "2022-01-20 00:00:00"),
                               b(["keqing"], "2021-02-17 00:00:00", "2021-03-02 00:00:00")]}  # standard now
        now = datetime.datetime(2021, 12, 10, tzinfo=UTC)
        r = {x["id"]: x for x in wiki.reruns(data, now=now)}
        self.assertEqual([x["id"] for x in wiki.reruns(data, now=now)], ["klee", "venti", "xiao", "zhongli"])
        self.assertEqual((r["venti"]["runs"], r["venti"]["last"].month), (2, 4))
        self.assertEqual((r["zhongli"]["status"], r["xiao"]["status"]), ("live", "next"))


if __name__ == "__main__":
    unittest.main()
