"""Browser tests: a real Chromium tab uses the calculator page."""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def calculate(page: Page, server_url: str, a: str, b: str, operation: str) -> None:
    page.goto(server_url)
    page.fill("#a", a)
    page.fill("#b", b)
    page.select_option("#type", operation)
    page.click("#calculate")


def test_page_loads(page: Page, server_url):
    page.goto(server_url)
    expect(page).to_have_title("Calculator")
    expect(page.locator("h1")).to_have_text("Calculator")
    expect(page.locator("#type option")).to_have_text(
        ["Add (a + b)", "Sub (a − b)", "Multiply (a × b)", "Divide (a ÷ b)"]
    )


@pytest.mark.parametrize(
    ("a", "b", "operation", "expected"),
    [
        ("10", "5", "Add", "Result: 15"),
        ("10", "5", "Sub", "Result: 5"),
        ("10", "5", "Multiply", "Result: 50"),
        ("10", "4", "Divide", "Result: 2.5"),
        ("-3", "1.5", "Add", "Result: -1.5"),
    ],
)
def test_calculations(page: Page, server_url, a, b, operation, expected):
    calculate(page, server_url, a, b, operation)
    expect(page.locator("#result")).to_have_text(expected)
    expect(page.locator("#result")).to_have_class("ok")


def test_divide_by_zero_shows_error(page: Page, server_url):
    calculate(page, server_url, "10", "0", "Divide")
    expect(page.locator("#result")).to_have_text("Error: b must not be zero for Divide")
    expect(page.locator("#result")).to_have_class("error")


def test_result_too_large_shows_error(page: Page, server_url):
    calculate(page, server_url, "1e308", "10", "Multiply")
    expect(page.locator("#result")).to_have_text("Error: Result is too large to store")


def test_missing_number_shows_error(page: Page, server_url):
    calculate(page, server_url, "10", "", "Add")
    expect(page.locator("#result")).to_have_text("Error: Please enter both numbers")


def test_new_result_replaces_error(page: Page, server_url):
    calculate(page, server_url, "1", "0", "Divide")
    expect(page.locator("#result")).to_have_class("error")

    page.fill("#b", "2")
    page.click("#calculate")
    expect(page.locator("#result")).to_have_text("Result: 0.5")
    expect(page.locator("#result")).to_have_class("ok")
