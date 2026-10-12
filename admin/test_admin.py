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
