from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path


def empty_history() -> dict:
    return {"version": 1, "products": {}}


def load_price_history(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return empty_history()
    if not isinstance(data, dict) or not isinstance(data.get("products"), dict):
        return empty_history()
    data.setdefault("version", 1)
    return data


def _quantity_key(item: dict) -> str:
    q = item.get("quantity") or {}
    stable = {
        key: q.get(key)
        for key in (
            "total_weight_g",
            "unit_weight_g",
            "unit_volume_ml",
            "total_volume_ml",
            "count",
        )
        if q.get(key) is not None
    }
    return json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _parse_day(value: str):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def apply_price_history(
    history: dict,
    category: dict,
    items: list[dict],
    today: date,
    retention_days: int = 45,
) -> None:
    products = history.setdefault("products", {})
    today_text = today.isoformat()
    retention_cutoff = today - timedelta(days=retention_days)
    thirty_cutoff = today - timedelta(days=30)
    metric = category["primary"]

    for item in items:
        quantity_key = _quantity_key(item)
        key = f"{category['id']}|{item['id']}"
        record = products.get(key)
        if not isinstance(record, dict):
            record = {
                "category_id": category["id"],
                "product_id": item["id"],
                "name": item["name"],
                "quantity_key": quantity_key,
                "points": [],
            }

        # A listing can be repurposed by a merchant. If the parsed quantity
        # changed, do not compare the new offer against the old package size.
        if record.get("quantity_key") != quantity_key:
            record["points"] = []
            record["quantity_key"] = quantity_key

        valid_points = []
        for point in record.get("points", []):
            day = _parse_day(point.get("date"))
            if not day or day < retention_cutoff:
                continue
            try:
                price = int(point["price"])
                unit = float(point["unit"])
            except (KeyError, TypeError, ValueError):
                continue
            valid_points.append({"date": day.isoformat(), "price": price, "unit": unit})

        prior = [p for p in valid_points if p["date"] < today_text]
        prior.sort(key=lambda p: p["date"])
        previous = prior[-1] if prior else None
        prior_30 = [
            p for p in prior
            if (_parse_day(p["date"]) or date.min) >= thirty_cutoff
        ]

        current_price = int(item["price"])
        current_unit = float(item["unit_prices"][metric])
        previous_day = _parse_day(previous["date"]) if previous else None
        previous_label = None
        if previous_day:
            previous_label = "昨日比" if previous_day == today - timedelta(days=1) else "前回比"

        price_delta = current_price - int(previous["price"]) if previous else None
        unit_delta = current_unit - float(previous["unit"]) if previous else None
        percent_delta = (
            (price_delta / float(previous["price"])) * 100
            if previous and previous["price"] else None
        )
        low_30_unit = min(
            [current_unit] + [float(p["unit"]) for p in prior_30]
        )
        is_30d_low = bool(prior_30) and current_unit <= low_30_unit + 1e-9

        observed_dates = {p["date"] for p in valid_points}
        observed_dates.add(today_text)
        series_30 = [
            {"date": p["date"], "price": int(p["price"]), "unit": float(p["unit"])}
            for p in prior_30
        ] + [{"date": today_text, "price": current_price, "unit": current_unit}]
        item["price_history"] = {
            "observed_days": len(observed_dates),
            "previous_date": previous["date"] if previous else None,
            "previous_price": int(previous["price"]) if previous else None,
            "previous_unit": float(previous["unit"]) if previous else None,
            "previous_label": previous_label,
            "price_delta": price_delta,
            "unit_delta": unit_delta,
            "percent_delta": percent_delta,
            "lowest_30d_unit": low_30_unit,
            "is_30d_low": is_30d_low,
            "series_30d": series_30,
        }

        valid_points = [p for p in valid_points if p["date"] != today_text]
        valid_points.append(
            {"date": today_text, "price": current_price, "unit": current_unit}
        )
        valid_points.sort(key=lambda p: p["date"])
        record.update(
            {
                "category_id": category["id"],
                "product_id": item["id"],
                "name": item["name"],
                "quantity_key": quantity_key,
                "points": valid_points,
            }
        )
        products[key] = record

    # Drop records that have no observation in the retention window.
    stale = []
    for key, record in products.items():
        points = record.get("points", []) if isinstance(record, dict) else []
        latest = max(
            (_parse_day(p.get("date")) for p in points),
            default=None,
        )
        if latest is None or latest < retention_cutoff:
            stale.append(key)
    for key in stale:
        products.pop(key, None)

    history["updated_at"] = today_text


def save_price_history(history: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
