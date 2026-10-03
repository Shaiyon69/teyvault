import json
import unittest

from teyvat import lansync


class TestLanSync(unittest.TestCase):
    def test_pull_with_pin_and_lockout(self):
        share = lansync.Share(json.dumps({"hk4e": []}).encode(), host="127.0.0.1")
        self.addCleanup(share.close)
        address = f"127.0.0.1:{share.port}"
        self.assertEqual(lansync.pull(address, share.pin), {"hk4e": []})
        wrong = "x" + share.pin[1:]
        for _ in range(lansync.MAX_BAD_PINS):
            with self.assertRaisesRegex(SystemExit, "Wrong PIN"):
                lansync.pull(address, wrong)
        with self.assertRaises(SystemExit):  # locked out, even with the right PIN
            lansync.pull(address, share.pin)


if __name__ == "__main__":
    unittest.main()
