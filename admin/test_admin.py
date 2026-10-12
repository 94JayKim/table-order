import unittest

from streamlit.testing.v1 import AppTest

from dummy_data import make_customers, make_orders


class AdminTest(unittest.TestCase):
    def test_all_pages_render_after_login(self):
        app = AppTest.from_file("app.py", default_timeout=30).run()
        app.text_input[0].set_value("owner")
        app.button[0].click().run()
        self.assertFalse(app.exception)
        for page in ["대시보드", "메뉴 관리", "추천 가중치", "고객 등급", "주문 이력", "마케팅"]:
            app.sidebar.radio[0].set_value(page).run()
            self.assertFalse(app.exception, page)

    def test_wrong_password(self):
        app = AppTest.from_file("app.py").run()
        app.text_input[0].set_value("x")
        app.button[0].click().run()
        self.assertTrue(app.error)

    def test_dummy_data(self):
        c = make_customers()
        self.assertEqual(len(make_orders(c)), 300)


if __name__ == "__main__":
    unittest.main()


class SensDemoTests(unittest.TestCase):
    def test_sms_lms_and_rules(self):
        from datetime import time
        import sens_demo as s
        self.assertEqual(s.msg_type("짧은 문자"), "SMS")
        self.assertEqual(s.msg_type("가" * 50), "LMS")
        used = {"SMS": 0, "LMS": 0}
        self.assertTrue(s.plan(10, "안녕", time(14, 0), used)["ok"])
        self.assertFalse(s.plan(10, "안녕", time(22, 0), used)["ok"])      # 야간
        self.assertFalse(s.plan(51, "안녕", time(14, 0), used)["ok"])      # 한도
        self.assertFalse(s.plan(0, "안녕", time(14, 0), used)["ok"])       # 대상 없음
        self.assertIn("(광고)", s.build_message("본문", "가게"))

    def test_marketing_page_send_updates_quota(self):
        app = AppTest.from_file("app.py", default_timeout=30).run()
        app.text_input[0].set_value("owner")
        app.button[0].click().run()
        app.sidebar.radio[0].set_value("마케팅").run()
        from datetime import time
        app.time_input[0].set_value(time(14, 0)).run()
        self.assertFalse(app.exception)
        send = [b for b in app.button if b.label == "발송 (데모)"][0]
        self.assertFalse(send.disabled)
        send.click().run()
        self.assertGreater(app.session_state["sms_used"]["SMS"] + app.session_state["sms_used"]["LMS"], 0)
