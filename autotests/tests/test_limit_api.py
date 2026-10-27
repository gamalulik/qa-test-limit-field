"""API-автотесты поля «Лимит расходов».

Кейсы зеркалят тест-дизайн из README (разделы 1-4, 7).
Запуск: pytest -v (из папки autotests).
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_card(limit_type, **kwargs):
    body = {"limit_type": limit_type, **kwargs}
    return client.post("/cards", json=body)


# --- 1. Позитивные значения ---------------------------------------------

@pytest.mark.parametrize(
    "value, expected",
    [
        (1, "1.00"),
        (100, "100.00"),
        (0.01, "0.01"),
        (10.50, "10.50"),
        (100.00, "100.00"),
        (999999999, "999999999.00"),
        (999999999.99, "999999999.99"),  # верхняя граница
    ],
)
def test_valid_limit_is_accepted_and_normalized(value, expected):
    resp = create_card("DAY", limit=value)
    assert resp.status_code == 201, resp.text
    assert resp.json()["limit"] == expected


@pytest.mark.parametrize("limit_type", ["DAY", "WEEK", "MONTH", "LIFETIME"])
def test_all_limit_types_accept_valid_value(limit_type):
    resp = create_card(limit_type, limit=100)
    assert resp.status_code == 201, resp.text


def test_no_limit_type_without_value():
    resp = create_card("NO_LIMIT")
    assert resp.status_code == 201, resp.text
    assert resp.json()["limit"] is None


# --- 2. Границы и точность ----------------------------------------------

@pytest.mark.parametrize(
    "value",
    [
        0,                  # ноль: «нет лимита» выражается типом NO_LIMIT
        0.001,              # больше двух знаков после точки
        10.505,             # округление не делаем молча - отклоняем
        1000000000,         # больше максимума
        9999999999999999,   # потенциальное переполнение
    ],
)
def test_out_of_range_or_precision_is_rejected(value):
    resp = create_card("DAY", limit=value)
    assert resp.status_code == 400, resp.text


def test_boundary_min_accepted():
    assert create_card("DAY", limit=0.01).status_code == 201


def test_just_below_min_rejected():
    assert create_card("DAY", limit=0.009).status_code == 400


# --- 3. Невалидный ввод (в обход UI) --------------------------------------

@pytest.mark.parametrize(
    "value",
    [
        -100,          # отрицательное
        "abc",         # строка с буквами
        "100",         # число строкой - тип должен быть числовым
        "10,50",       # запятая как разделитель
        "1.2.3",       # две точки
        "$100",        # знак валюты
        "1 000",       # пробел внутри
        " 100 ",       # пробелы по краям
        "1e5",         # экспоненциальная запись строкой
        "<script>alert(1)</script>",  # XSS-строка
        "' OR 1=1",    # SQL-инъекция строкой
        True,          # bool не является суммой
        [100],         # массив
        {"v": 100},    # объект
    ],
)
def test_invalid_limit_value_is_rejected(value):
    resp = create_card("DAY", limit=value)
    assert resp.status_code == 400, resp.text


def test_missing_limit_for_day_is_rejected():
    resp = create_card("DAY")
    assert resp.status_code == 400, resp.text


def test_null_limit_for_day_is_rejected():
    resp = create_card("DAY", limit=None)
    assert resp.status_code == 400, resp.text


def test_infinity_is_rejected():
    # 1e308 * 10 == inf; json не сериализует inf, поэтому шлём большой float
    resp = create_card("DAY", limit=1e308)
    assert resp.status_code == 400, resp.text


# --- 4. Связка с типом лимита ---------------------------------------------

def test_limit_with_no_limit_type_is_rejected():
    resp = create_card("NO_LIMIT", limit=100)
    assert resp.status_code == 400, resp.text


@pytest.mark.parametrize("limit_type", ["", "YEAR", "day", None, 123])
def test_unknown_limit_type_is_rejected(limit_type):
    resp = client.post("/cards", json={"limit_type": limit_type, "limit": 100})
    assert resp.status_code == 400, resp.text


# --- 8. После сохранения ---------------------------------------------------

def test_saved_card_is_returned_in_list_with_normalized_limit():
    created = create_card("MONTH", limit=10.5).json()
    cards = client.get("/cards").json()
    saved = next(c for c in cards if c["id"] == created["id"])
    assert saved["limit"] == "10.50"
    assert saved["limit_type"] == "MONTH"
