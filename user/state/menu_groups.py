"""매운맛 단계만 다른 메뉴를 한 메뉴로 묶는 규칙 (화면 전용, 메뉴 데이터/주문 구조는 그대로).

규칙: 같은 카테고리에서 이름이 `<메뉴명> (순한맛|보통맛|아주 매운맛)` 꼴이고 `<메뉴명>` 이 같은 항목이 2개 이상이면
한 그룹으로 본다. 그룹은 목록에서 첫 번째 항목 자리에 나타나고, 단계는 순한맛 → 보통맛 → 아주 매운맛 순이다.
"""

import re

SPICY_LABELS = ("순한맛", "보통맛", "아주 매운맛")
_PATTERN = re.compile(r"^(?P<base>.+?) \((?P<label>" + "|".join(SPICY_LABELS) + r")\)$")


def split_spicy_name(name):
    """'골뱅이 소면 무침 (보통맛)' → ('골뱅이 소면 무침', '보통맛'). 해당 꼴이 아니면 None."""
    m = _PATTERN.match(name)
    return (m["base"], m["label"]) if m else None


def group_spicy_variants(items):
    """메뉴 목록을 [{"type": "item", "item": m} | {"type": "group", "id", "name", "variants": [(label, m), ...]}] 로 바꾼다."""
    buckets = {}
    for m in items:
        parsed = split_spicy_name(m["name"])
        if parsed:
            buckets.setdefault((m["cat"], parsed[0]), []).append((parsed[1], m))
    entries, seen = [], set()
    for m in items:
        parsed = split_spicy_name(m["name"])
        key = (m["cat"], parsed[0]) if parsed else None
        if key is None or len(buckets[key]) < 2:
            entries.append({"type": "item", "item": m})
        elif key not in seen:
            seen.add(key)
            variants = sorted(buckets[key], key=lambda v: SPICY_LABELS.index(v[0]))
            entries.append({"type": "group", "id": variants[0][1]["id"], "name": parsed[0], "variants": variants})
    return entries
