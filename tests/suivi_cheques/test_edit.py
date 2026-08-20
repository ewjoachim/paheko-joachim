"""Edit pages: the month is picked from a dropdown (12 months); the year is
deduced from the cheque's reception date and stored as YYYY-MM."""

import datetime

import pytest
from playwright.sync_api import Page, expect

# seed-demo.php dates every till payment 2026-07-01. The encashment year is the
# next occurrence of the picked month at or after that date, so a month before
# July rolls over to 2027 — the exercise plays no part in it.
RECEIVED = datetime.date(2026, 7, 1)


def resolved_month(month: int) -> str:
    year = RECEIVED.year + (1 if month < RECEIVED.month else 0)
    return f"{year:04d}-{month:02d}"


@pytest.mark.parametrize("month", [9, 3], ids=["same-year", "next-year"])
def test_edit_planned_month_via_dropdown(
    admin_page: Page, module_url, reseed, seed, month
):
    reseed()
    pid = seed["pay_edit"]  # CHQ-0140, a plain (unlocked) cheque
    admin_page.goto(f"{module_url}/edit.html?payment={pid}", wait_until="domcontentloaded")

    # The month field is a <select> of the 12 months, not a free-text YYYY-MM.
    expect(admin_page.locator('select[name="planned_month"]')).to_have_count(1)
    admin_page.select_option('select[name="planned_month"]', str(month))
    admin_page.get_by_role("button", name="Enregistrer").click()
    admin_page.wait_for_load_state("domcontentloaded")

    # September stays in the reception year; March lands in the following one.
    admin_page.goto(
        f"{module_url}/index.html?month={resolved_month(month)}",
        wait_until="domcontentloaded",
    )
    expect(admin_page.locator("table.list", has_text="CHQ-0140")).to_have_count(1)


def test_method_month_year_follows_reception(
    admin_page: Page, module_url, reseed, till_payment
):
    """Without an overlay the month comes from the payment method (seeded method 2
    = January) and its year from the reception date, not from the accounting
    exercise. A cheque handed over in July is therefore collected in January of
    the FOLLOWING year — the pre-registration case: cheques taken before the
    exercise they belong to has started must not land in a past month, where the
    deposit slip would sweep them straight to the bank."""
    reseed()
    till_payment(method=2, date="2026-07-01", amount=4200, reference="CHQ-0400")

    admin_page.goto(f"{module_url}/index.html?month=2027-01", wait_until="domcontentloaded")
    expect(admin_page.locator("table.list", has_text="CHQ-0400")).to_have_count(1)

    admin_page.goto(f"{module_url}/index.html?month=2026-01", wait_until="domcontentloaded")
    expect(admin_page.locator("table.list", has_text="CHQ-0400")).to_have_count(0)

    # And it is not due yet, so it stays out of a slip prepared for July 2026.
    admin_page.goto(f"{module_url}/deposit.html?month=2026-07", wait_until="domcontentloaded")
    expect(admin_page.locator("table.list", has_text="CHQ-0400")).to_have_count(0)


def test_module_cheque_opens_with_month_dropdown(admin_page: Page, module_url, reseed):
    reseed()
    # Seeded settling cheque CHQ-0200 (planned 2026-09).
    admin_page.goto(
        f"{module_url}/edit.html?key=chq-regl-demo-0200",
        wait_until="domcontentloaded",
    )
    assert admin_page.locator(".error, .exception").count() == 0
    select = admin_page.locator('select[name="planned_month"]')
    expect(select).to_have_count(1)
    # September (9) is preselected from the stored 2026-09.
    assert admin_page.eval_on_selector(
        'select[name="planned_month"]', "el => el.value"
    ) == "9"
