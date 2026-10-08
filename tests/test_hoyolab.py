import base64
import json
import unittest

from teyvat import hoyolab


class TestLogin(unittest.TestCase):
    def test_login_key_layout(self):
        der = base64.b64decode(hoyolab.LOGIN_KEY)
        self.assertEqual(der[28:33], bytes.fromhex("0282010100"))  # 256-byte modulus starts at 33
        self.assertEqual(der[289:], bytes.fromhex("0203010001"))  # exponent 65537

    def test_rsa_encrypt_is_padded_and_random(self):
        a, b = hoyolab.rsa_encrypt("me@example.com"), hoyolab.rsa_encrypt("me@example.com")
        self.assertEqual(len(base64.b64decode(a)), 256)
        self.assertNotEqual(a, b)

    def test_captcha_required_reads_aigis(self):
        need = hoyolab.CaptchaRequired({"session_id": "s1", "mmt_type": 1,
                                        "data": json.dumps({"success": 1, "gt": "g", "challenge": "c"})})
        self.assertEqual((need.session_id, need.gt, need.challenge, need.retcode), ("s1", "g", "c", -3101))


if __name__ == "__main__":
    unittest.main()


class TestCalculator(unittest.TestCase):
    def test_item_raises_only_the_three_talents_and_never_lowers(self):
        detail = {"weapon": {"id": 11501, "level_current": 90, "max_level": 90},
                  "skill_list": [{"id": 1, "group_id": 101, "level_current": 6, "max_level": 10},
                                 {"id": 2, "group_id": 102, "level_current": 10, "max_level": 10},
                                 {"id": 3, "group_id": 103, "level_current": 1, "max_level": 10},
                                 {"id": 4, "group_id": 104, "level_current": 0, "max_level": 1}]}
        item = hoyolab.calc_item(10000002, 80, detail, 90, 9, 90)
        self.assertEqual(item["avatar_level_target"], 90)
        self.assertEqual([(t["id"], t["level_target"]) for t in item["skill_list"]], [(101, 9), (102, 10), (103, 9)])
        self.assertEqual(item["weapon"]["level_target"], 90)
