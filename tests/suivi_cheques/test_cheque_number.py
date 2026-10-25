"""A cheque number typed wrong can be corrected in the module. For a till cheque
the till keeps its own number (a closed tab cannot be edited); the module's
correction wins everywhere it shows a number, the deposit slip first of all."""

import re

from playwright.sync_api import Page, expect

JULY_TODO = "index.html?period=2026-07&state=todo"


def _set_number(page: Page, url: str, number: str) -> None:
    page.goto(url, wait_until="domcontentloaded")
    page.fill('input[name="cheque_number"]', number)
    page.get_by_role("button", name="Enregistrer").click()
    page.wait_for_load_state("domcontentloaded")


def test_corrected_till_number_reaches_the_slip(
    admin_page: Page, module_url, reseed, seed, add_to_slip
):
    reseed()
    _set_number(admin_page, f"{module_url}/edit.html?payment={seed['pay_edit']}", "CHQ-9140")

    admin_page.goto(f"{module_url}/{JULY_TODO}", wait_until="domcontentloaded")
    row = admin_page.locator("#cheques tr", has_text="CHQ-9140")
    expect(row).to_have_count(1)
    expect(row).to_contain_text("caisse : CHQ-0140")

    admin_page.get_by_role("button", name="Tout cocher").click()
    add_to_slip(admin_page)
    assert re.search(r"[?&]batch=", admin_page.url)
    expect(admin_page.locator("table", has_text="CHQ-9140")).to_have_count(1)
    expect(admin_page.locator("table", has_text="CHQ-0140")).to_have_count(0)


def test_emptying_the_field_falls_back_to_the_till_number(
    admin_page: Page, module_url, reseed, seed
):
    reseed()
    url = f"{module_url}/edit.html?payment={seed['pay_edit']}"
    _set_number(admin_page, url, "CHQ-9140")
    _set_number(admin_page, url, "")

    admin_page.goto(f"{module_url}/{JULY_TODO}", wait_until="domcontentloaded")
    row = admin_page.locator("#cheques tr", has_text="CHQ-0140")
    expect(row).to_have_count(1)
    expect(row).not_to_contain_text("caisse :")


def test_module_cheque_number_is_editable(admin_page: Page, module_url, reseed):
    reseed()
    url = f"{module_url}/edit.html?key=chq-regl-demo-0200"
    _set_number(admin_page, url, "CHQ-9200")

    admin_page.goto(f"{module_url}/index.html?period=2026-09&state=all", wait_until="domcontentloaded")
    expect(admin_page.locator("#cheques tr", has_text="CHQ-9200")).to_have_count(1)
    expect(admin_page.locator("#cheques tr", has_text="CHQ-0200")).to_have_count(0)

    # A module cheque has no other number to fall back on.
    admin_page.goto(url, wait_until="domcontentloaded")
    expect(admin_page.locator('input[name="cheque_number"]')).to_have_attribute("required", "required")
