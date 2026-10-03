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
