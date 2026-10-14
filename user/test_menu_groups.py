import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from user.menu_data import MENU
from user.state.menu_groups import group_spicy_variants, split_spicy_name


def _m(id_, name, price=1000, cat="anju"):
    return {"id": id_, "cat": cat, "name": name, "price": price}


class MenuGroupTests(unittest.TestCase):
    def test_split_name(self):
        self.assertEqual(split_spicy_name("골뱅이 소면 무침 (아주 매운맛)"), ("골뱅이 소면 무침", "아주 매운맛"))
        self.assertIsNone(split_spicy_name("순대볶음"))
        self.assertIsNone(split_spicy_name("역전 옛날통닭 (한 마리·양념)"))

    def test_groups_in_level_order_at_first_position(self):
        items = [_m("x", "닭발 (아주 매운맛)", 2000), _m("y", "계란말이"), _m("z", "닭발 (순한맛)", 1000), _m("w", "닭발 (보통맛)", 1500)]
        entries = group_spicy_variants(items)
        self.assertEqual([e["type"] for e in entries], ["group", "item"])
        group = entries[0]
        self.assertEqual(group["name"], "닭발")
        self.assertEqual([(label, m["id"]) for label, m in group["variants"]], [("순한맛", "z"), ("보통맛", "w"), ("아주 매운맛", "x")])
        self.assertEqual(group["id"], "z")

    def test_single_variant_or_other_category_is_not_grouped(self):
        entries = group_spicy_variants([_m("a", "닭발 (순한맛)"), _m("b", "닭발 (보통맛)", cat="soup")])
        self.assertEqual([e["type"] for e in entries], ["item", "item"])

    def test_real_menu(self):
        groups = [e for e in group_spicy_variants(MENU) if e["type"] == "group"]
        self.assertEqual([g["name"] for g in groups], ["골뱅이 소면 무침", "직화 무뼈닭발"])
        grouped_ids = {m["id"] for g in groups for _, m in g["variants"]}
        self.assertEqual(grouped_ids, {"a2", "a2-medium", "a2-hot", "a3", "a3-medium", "a3-hot"})


if __name__ == "__main__":
    unittest.main()
