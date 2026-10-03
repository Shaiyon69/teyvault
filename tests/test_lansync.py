import json
import unittest
import urllib.error
import urllib.request

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

    def test_second_share_gets_its_own_port(self):
        a = lansync.Share(b"1", host="127.0.0.1")
        self.addCleanup(a.close)
        b = lansync.Share(b"2", host="127.0.0.1")
        self.addCleanup(b.close)
        self.assertNotEqual(a.port, b.port)
        self.assertEqual(lansync.pull(f"127.0.0.1:{b.port}", b.pin), 2)

    def test_other_paths_cost_no_pin_try(self):
        share = lansync.Share(b"1", host="127.0.0.1")
        self.addCleanup(share.close)
        for _ in range(lansync.MAX_BAD_PINS):
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(f"http://127.0.0.1:{share.port}/favicon.ico")
        self.assertEqual(lansync.pull(f"127.0.0.1:{share.port}", share.pin), 1)


if __name__ == "__main__":
    unittest.main()
