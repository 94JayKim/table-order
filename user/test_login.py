import unittest

from streamlit.testing.v1 import AppTest

import login_demo as ld


class LoginStateTests(unittest.TestCase):
    def test_happy_path_and_single_use(self):
        s = ld.new_session(0)
        self.assertFalse(ld.approve(s, 1, {"nickname": "a"}))  # 스캔 전 승인 불가
        self.assertTrue(ld.scan(s, 1))
        self.assertTrue(ld.approve(s, 2, {"nickname": "a"}))
        self.assertEqual(ld.state(s, 9999), "logged_in")
        self.assertFalse(ld.approve(s, 3, {"nickname": "b"}))  # 재사용 불가
        self.assertEqual(s["member"]["nickname"], "a")

    def test_expiry(self):
        s = ld.new_session(0)
        self.assertEqual(ld.state(s, ld.TTL_SECONDS + 1), "expired")
        self.assertFalse(ld.scan(s, ld.TTL_SECONDS + 1))


class LoginAppTests(unittest.TestCase):
    def test_qr_login_flow_gives_bonus_spin(self):
        app = AppTest.from_file("app.py", default_timeout=30).run()
        app.button(key="roulette_btn").click().run()
        self.assertTrue(app.session_state["roulette"])
        app.button(key="login_scan").click().run()
        app.button(key="login_approve").click().run()
        self.assertEqual(app.session_state["member"]["nickname"], "카카오손님")
        self.assertIsNone(app.session_state["roulette"])  # 룰렛 한 번 더
        self.assertFalse(app.exception)

    def test_expired_qr_can_be_refreshed(self):
        app = AppTest.from_file("app.py", default_timeout=30).run()
        old = app.session_state["login"]["token"]
        app.button(key="login_expire").click().run()
        self.assertTrue(app.button(key="login_scan").disabled)
        app.button(key="login_refresh").click().run()
        self.assertNotEqual(app.session_state["login"]["token"], old)


if __name__ == "__main__":
    unittest.main()
