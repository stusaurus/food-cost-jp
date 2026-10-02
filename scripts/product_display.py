"""Conservative display-only cleanup for Rakuten product titles.

Raw titles stay available for quantity/category validation. This module only
removes promotion-only wrappers/prefixes/suffixes and never rewrites product
identity text such as brand, capacity, count or product name.
"""
from __future__ import annotations

import re
import unicodedata

PROMO = re.compile(
    r"(?:最大\s*)?[\d,]+\s*(?:円|%)\s*(?:OFF|オフ|引き?|値引き)(?:\s*(?:クーポン|coupon))?"
    r"|(?:クーポン|coupon)(?:利用)?で?\s*(?:最大\s*)?[\d,]+\s*(?:円|%)\s*(?:OFF|オフ|引き?)?"
    r"|(?:全品\s*)?(?:ポイント\s*|P\s*)(?:最大\s*)?\d+\s*倍"
    r"|\d+\s*時間限定|本日(?:限定|限り)|期間限定|数量限定"
    r"|お買い物マラソン|マラソン(?:中|期間中|限定)|食いしんぼう祭|イーグルス勝利"
    r"|楽天(?:スーパー)?SALE|スーパーSALE|タイムセール|SALE|セール(?:中|開催中)?"
    r"|送料無料|送料込み|クーポン(?:あり|配布中|対象)|トップページにクーポンバナー"
    r"|総額[\d,]+(?:万|億)?ポイントが当たる|エントリーで|最強配送|最短翌日お届け|365日出荷"
    r"|特売|売り尽くし|在庫限り|無くなり次第終了|大赤字特価|特価"
    r"|(?:ケースがお得\s*)?1本(?:あたり|当たり)\s*[\d,.]+\s*円(?:税別)?(?:[~〜～])?"
    r"|[\d,]+\s*円\s*ポッキリ|(?:楽天)?ランキング(?:受賞|\s*\d+\s*位)",
    re.I,
)
DATE = re.compile(
    r"(?:\d{1,2}/\d{1,2}|\d{1,2}月\d{1,2}日)(?:\s*\([^)]*\))?(?:限定|限り)?"
)
TIME = re.compile(
    r"(?:[~〜～]\s*)?\d{1,2}日?\s*\d{1,2}:\d{2}(?:迄|まで)?"
    r"|\d{1,2}:\d{2}(?:迄|まで)?|\d{1,2}時(?:迄|まで)?"
)
EVENT_NOISE = re.compile(
    r"(?:要エントリー|エントリー必須|先着|今だけ|限定開催|開催中|対象商品|対象ショップ|レビュー投稿で|全品)",
    re.I,
)
LEADING_LABEL = re.compile(r"^\s*(?:【([^】]+)】|\[([^\]]+)\]|＼([^／]+)／|《([^》]+)》|\(([^)]+)\))\s*")
TRAILING_LABEL = re.compile(r"\s*(?:【([^】]+)】|\[([^\]]+)\]|＼([^／]+)／|《([^》]+)》|\(([^)]+)\))\s*$")
ANY_LABEL = re.compile(r"(?:【([^】]+)】|\[([^\]]+)\]|＼([^／]+)／|《([^》]+)》)")


def _nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or ""))


def promotion_only(label: str) -> bool:
    text = _nfkc(label)
    if not (PROMO.search(text) or DATE.search(text) or TIME.search(text)):
        return False
    rest = PROMO.sub("", text)
    rest = DATE.sub("", rest)
    rest = TIME.sub("", rest)
    rest = EVENT_NOISE.sub("", rest)
    rest = re.sub(r"(?:まで|迄|から|より|限定|対象|開催|中)", "", rest)
    # Product identity must win over cleanup. Any remaining word/number keeps it.
    return not re.sub(r"[\s★☆彡!！?？+＋・／/、。~〜～:：%％\-_=<>｜|]", "", rest)


def _promotion_group(match: re.Match) -> str:
    return next(group for group in match.groups() if group is not None)


def clean_display_name(name: str) -> str:
    original = str(name or "").strip()
    text = original
    # Some merchants put a complete promotional unit-price claim in //...//.
    # Remove that wrapper only, leaving actual package quantities untouched.
    text = re.sub(r"^\s*//[^/]*(?:マラソン|オフ|OFF)[^/]*//\s*", '', text, flags=re.I)
    text = re.sub(r"^[\\＼]売り切り商品が激熱価格[!！]*[／/]\s*", '', text)

    while match := LEADING_LABEL.match(text):
        if not promotion_only(_promotion_group(match)):
            break
        remainder = text[match.end():].lstrip()
        if not remainder:
            break
        text = remainder

    while match := TRAILING_LABEL.search(text):
        if not promotion_only(_promotion_group(match)):
            break
        remainder = text[:match.start()].rstrip()
        if not remainder:
            break
        text = remainder

    # Promotion-only bracket labels are safe to remove even when an identity
    # label such as 【新米】 appears before them.
    def strip_label(match: re.Match) -> str:
        label = _promotion_group(match)
        if promotion_only(label):
            return " "

        normalized = _nfkc(label).strip()
        # Preserve crop-year identity while removing a promo-only suffix.
        year_match = re.fullmatch(r"(\d{1,2}年産)(.+)", normalized)
        if year_match:
            suffix = re.sub(r"^最終", "", year_match.group(2))
            suffix = suffix.replace("の大赤字特価", "大赤字特価")
            if promotion_only(suffix):
                return f"【{year_match.group(1)}】"

        # "訳あり" is product-condition information; the price callout is not.
        bargain_match = re.fullmatch(
            r"(訳あり商品)(?:が)?\s*([\d,]+\s*円\s*ポッキリ[!！]?)",
            normalized,
        )
        if bargain_match and promotion_only(bargain_match.group(2)):
            return f"【{bargain_match.group(1)}】"

        return match.group(0)

    text = ANY_LABEL.sub(strip_label, text)

    # Bare exact promotion prefixes. Unknown/mixed wording is intentionally kept.
    bare = re.compile(
        r"^\s*(?:(?:送料無料|送料込み|本日限定|本日限り|お買い物マラソン|食いしんぼう祭|イーグルス勝利|"
        r"楽天(?:スーパー)?SALE|スーパーSALE|タイムセール|SALE|セール中?|楽天ランキング受賞|特売)"
        r"\s*[!！★☆＋+・|｜:：\-/／]*\s*)+",
        re.I,
    )
    text = bare.sub("", text)

    # A leading standalone numeric coupon phrase is safe to remove only when it
    # is followed by clear punctuation/whitespace and real product text remains.
    coupon_prefix = re.compile(
        r"^\s*(?:(?:クーポン(?:利用)?で?\s*)?(?:最大\s*)?[\d,]+\s*(?:円|%)\s*(?:OFF|オフ|引き?)"
        r"(?:\s*クーポン(?:あり|対象)?)?|(?:最大\s*)?[\d,]+\s*(?:円|%)\s*(?:OFF|オフ|引き?)\s*クーポン(?:あり)?)"
        r"\s*(?:★?\s*(?:先着順?|食いしんぼう祭|イーグルス勝利))?"
        r"\s*[!！★☆＋+・|｜:：\-/／]*\s*",
        re.I,
    )
    candidate = coupon_prefix.sub("", text)
    if candidate.strip():
        text = candidate

    text = re.sub(r"(?<!\S)送料無料(?![※(（])", " ", text)
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned or original
