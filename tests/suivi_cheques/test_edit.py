"""Edit pages: the month is picked from a dropdown (12 months); the year is
deduced from the current exercise and stored as YYYY-MM."""

import datetime

from playwright.sync_api import Page, expect

# The bootstrap opens an exercise spanning the current calendar year, starting in
# January — so any picked month resolves to that same year.
YEAR = datetime.date.today().year


def test_edit_planned_month_via_dropdown(admin_page: Page, module_url, reseed, seed):
    reseed()
    pid = seed["pay_edit"]  # CHQ-0140, a plain (unlocked) cheque
    admin_page.goto(f"{module_url}/edit.html?payment={pid}", wait_until="domcontentloaded")

    # The month field is a <select> of the 12 months, not a free-text YYYY-MM.
    expect(admin_page.locator('select[name="planned_month"]')).to_have_count(1)
    admin_page.select_option('select[name="planned_month"]', "3")  # Mars
    admin_page.get_by_role("button", name="Enregistrer").click()
    admin_page.wait_for_load_state("domcontentloaded")

    # Stored as <year>-03: the cheque now shows under March of the exercise year.
    admin_page.goto(f"{module_url}/index.html?month={YEAR}-03", wait_until="domcontentloaded")
    expect(admin_page.locator("table.list", has_text="CHQ-0140")).to_have_count(1)


def test_edit_replacement_opens_with_month_dropdown(admin_page: Page, module_url, reseed):
    reseed()
    # Seeded replacement cheque CHQ-0200 (planned 2026-09).
    admin_page.goto(
        f"{module_url}/edit_replacement.html?key=rempl-demo-0200",
        wait_until="domcontentloaded",
    )
    assert admin_page.locator(".error, .exception").count() == 0
    select = admin_page.locator('select[name="planned_month"]')
    expect(select).to_have_count(1)
    # September (9) is preselected from the stored 2026-09.
    assert admin_page.eval_on_selector(
        'select[name="planned_month"]', "el => el.value"
    ) == "9"
