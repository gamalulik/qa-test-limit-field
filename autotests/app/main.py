"""Мок-сервис поля «Лимит расходов».

Реализует допущения из тест-дизайна (README в корне репо):
- валюта с точностью до цента (2 знака после точки);
- минимальный лимит 0.01, максимальный 999999999.99;
- при типе NO_LIMIT поле limit передаваться не должно;
- limit принимается только числом (не строкой), валидация на бэке.
"""

from decimal import Decimal, InvalidOperation

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Spending limit mock")

LIMIT_TYPES = {"NO_LIMIT", "DAY", "WEEK", "MONTH", "LIFETIME"}
MIN_LIMIT = Decimal("0.01")
MAX_LIMIT = Decimal("999999999.99")

_cards: list[dict] = []


def _error(message: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": message})


@app.post("/cards", status_code=201)
async def create_card(request: Request):
    try:
        body = await request.json()
    except Exception:
        return _error("body must be valid JSON")

    if not isinstance(body, dict):
        return _error("body must be an object")

    limit_type = body.get("limit_type")
    if limit_type not in LIMIT_TYPES:
        return _error(f"limit_type must be one of {sorted(LIMIT_TYPES)}")

    has_limit = "limit" in body and body["limit"] is not None

    if limit_type == "NO_LIMIT":
        if has_limit:
            return _error("limit must not be set when limit_type is NO_LIMIT")
        card = {"id": len(_cards) + 1, "limit_type": limit_type, "limit": None}
        _cards.append(card)
        return card

    if not has_limit:
        return _error("limit is required for this limit_type")

    raw = body["limit"]
    # bool в Python — подкласс int, отсекаем явно
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return _error("limit must be a number")

    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        return _error("limit must be a finite number")

    if not value.is_finite():
        return _error("limit must be a finite number")

    if value < MIN_LIMIT:
        return _error(f"limit must be at least {MIN_LIMIT}")

    if value > MAX_LIMIT:
        return _error(f"limit must not exceed {MAX_LIMIT}")

    if value != value.quantize(Decimal("0.01")):
        return _error("limit must have at most 2 decimal places")

    card = {
        "id": len(_cards) + 1,
        "limit_type": limit_type,
        "limit": str(value.quantize(Decimal("0.01"))),
    }
    _cards.append(card)
    return card


@app.get("/cards")
async def list_cards():
    return _cards
