"""Fail-closed food-category eligibility and duplicate helpers."""
from __future__ import annotations

import re
import unicodedata


REQUIRED = {
    "pack-rice": re.compile(r"パック\s*(?:ご飯|ごはん)|包装米飯|レンジ.{0,8}(?:ご飯|ごはん)|レトルト.{0,8}(?:ご飯|ごはん)", re.I),
    "rice": re.compile(r"(?:無洗米|白米|玄米|精米|新米|お米|\b米\b|米\s*\d)", re.I),
    "carbonated-water": re.compile(r"炭酸水|強炭酸|天然炭酸|スパークリング(?:ウォーター|水)", re.I),
    "oatmeal": re.compile(r"オートミール|オーツ麦|オート麦", re.I),
}

EXCLUDED = {
    "pack-rice": re.compile(r"おかゆ|お粥|雑炊|リゾット|チャーハン|炒飯|ピラフ|赤飯|おこわ|炊き込み|カレー|もち麦|雑穀|ふるさと納税|返礼品", re.I),
    "rice": re.compile(r"パック\s*(?:ご飯|ごはん)|包装米飯|米粉|米油|米びつ(?!当番)|炊飯器|甘酒|麹|こうじ|せんべい|煎餅|おかき|餅|もち米|ふるさと納税|返礼品", re.I),
    "carbonated-water": re.compile(r"シロップ|炭酸メーカー|ソーダメーカー|ソーダストリーム|ガスシリンダ|ガスボンベ|カートリッジ|ふるさと納税|返礼品", re.I),
    "oatmeal": re.compile(r"クッキー|ビスケット|シリアルバー|プロテインバー|スープ|リゾット|ふるさと納税|返礼品", re.I),
}

COMMON_EXCLUDED = re.compile(
    r"法人(?:様)?(?:限定|専用)|個人宅(?:配送|配達)?不可|業務専用会員|"
    r"定期購入(?:のみ)?|定期便(?:のみ)?|初回限定|会員限定|新規限定",
    re.I,
)


def normalize(text: str) -> str:
    return (
        unicodedata.normalize("NFKC", str(text or ""))
        .replace("×", "x")
        .replace("✕", "x")
        .replace("＊", "x")
        .replace("*", "x")
        .replace(",", "")
    )


def category_rejection(category_id: str, title: str):
    if category_id not in REQUIRED:
        return "unknown_category"
    text = normalize(title)
    if not text.strip():
        return "missing_title"
    if COMMON_EXCLUDED.search(text):
        return "restricted_or_limited_purchase"
    if EXCLUDED[category_id].search(text):
        return "wrong_product_type"
    if not REQUIRED[category_id].search(text):
        return "missing_category_evidence"
    return None


def quantity_conflict(title: str, category_id: str, quantity: dict) -> bool:
    """Reject visible secondary pack counts that the parser did not account for."""
    text = normalize(title)
    # Purchase-threshold gifts are not package quantity (e.g. 2個以上購入で特典).
    text = re.sub(r"\d+\s*個以上購入で[^】\]]*(?=[】\]]|$)", " ", text)
    evidence = normalize(quantity.get("evidence") or "")
    if evidence:
        text = text.replace(evidence, " ", 1)

    expected = int(quantity.get("count") or 1)
    # A remaining inner-pack decomposition is harmless when it exactly
    # reconciles to the parsed total, e.g. 48本 (24本×2ケース).
    if category_id == "carbonated-water":
        def remove_consistent_case(match):
            inner, outer = int(match.group(1)), int(match.group(2))
            return " " if inner * outer == expected else match.group(0)
        text = re.sub(
            r"(\d+)\s*本(?:入)?\s*x\s*(\d+)\s*(?:ケース|箱|セット)",
            remove_consistent_case,
            text,
            flags=re.I,
        )

    if category_id == "pack-rice":
        units = r"食|個|パック|ケース|箱|セット|袋"
    elif category_id == "carbonated-water":
        units = r"本|個|缶|パック|ケース|箱|セット"
    else:
        units = r"袋|個|パック|ケース|箱|セット"

    visible = [
        int(v)
        for v in re.findall(rf"(?<!\d)(\d+)\s*(?:{units})", text, flags=re.I)
        if int(v) > 1
    ]
    # Repeated wording of the already parsed count is harmless; a different
    # visible count means an outer case/set or variant that would change total.
    return any(value != expected for value in visible)


def quantity_signature(category_id: str, quantity: dict):
    if category_id == "carbonated-water":
        return (
            round(float(quantity.get("unit_volume_ml") or 0), 3),
            int(quantity.get("count") or 0),
            round(float(quantity.get("total_volume_ml") or 0), 3),
        )
    return (
        round(float(quantity.get("unit_weight_g") or 0), 3),
        int(quantity.get("count") or 0),
        round(float(quantity.get("total_weight_g") or 0), 3),
    )


def product_fingerprint(display_name: str) -> str:
    text = normalize(display_name).lower()
    text = re.sub(r"送料無料|送料込み", "", text)
    return re.sub(r"[^0-9a-zぁ-んァ-ヶ一-龠]", "", text)
