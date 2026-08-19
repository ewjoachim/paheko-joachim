"""Selecting which cheques go into a deposit slip.

The checkbox has to be *visible*: Paheko hides the real <input> (opacity: 0) and
draws the box through the <label> its `input` helper emits, inside a
`<td class="check">`. A bare <input> in a plain <td> is present, submits, and
passes every functional test — while showing nothing on screen. Hence the
computed-opacity assertion below: Playwright's is_visible() ignores opacity and
reports such a checkbox as visible.
"""

from playwright.sync_api import Page, expect

MONTH = "2026-09"  # 4 eligible cheques in the demo fixture
BOXES = 'table.list tbody td.check input[type="checkbox"][name^="deposit["]'


def test_checkbox_is_actually_drawn(admin_page: Page, module_url, reseed):
    reseed()
    admin_page.goto(f"{module_url}/deposit.html?month={MONTH}", wait_until="domcontentloaded")

    boxes = admin_page.locator(BOXES)
    expect(boxes).to_have_count(4)

    # The <label> is what the user sees and clicks.
    label = admin_page.locator("table.list tbody td.check label").first
    expect(label).to_have_count(1)
    box = label.bounding_box()
    assert box and box["width"] > 0 and box["height"] > 0, f"label has no box: {box}"
    opacity = label.evaluate("el => getComputedStyle(el).opacity")
    assert float(opacity) > 0, f"the drawn checkbox is transparent (opacity={opacity})"


def test_unchecked_by_default(admin_page: Page, module_url, reseed):
    """Ticking a cheque means "I have it in hand", so it must be deliberate."""
    reseed()
    admin_page.goto(f"{module_url}/deposit.html?month={MONTH}", wait_until="domcontentloaded")
    expect(admin_page.locator(f"{BOXES}:checked")).to_have_count(0)

    # Generating without ticking anything freezes nothing and says so.
    admin_page.get_by_role("button", name="Générer").click()
    admin_page.wait_for_load_state("domcontentloaded")
    expect(admin_page.locator(".error")).to_contain_text("Aucun chèque éligible sélectionné")


def test_header_toggle_checks_and_unchecks_all(admin_page: Page, module_url, reseed):
    reseed()
    admin_page.goto(f"{module_url}/deposit.html?month={MONTH}", wait_until="domcontentloaded")

    toggle = admin_page.locator("table.list thead td.check input[type=checkbox]")
    expect(toggle).to_have_count(1)

    toggle.check()
    expect(admin_page.locator(f"{BOXES}:checked")).to_have_count(4)
    toggle.uncheck()
    expect(admin_page.locator(f"{BOXES}:checked")).to_have_count(0)


def test_only_ticked_cheques_are_deposited(admin_page: Page, module_url, reseed):
    reseed()
    admin_page.goto(f"{module_url}/deposit.html?month={MONTH}", wait_until="domcontentloaded")

    rows = admin_page.locator("table.list tbody tr")
    kept = rows.nth(0).locator("td").nth(2).inner_text()
    dropped = rows.nth(1).locator("td").nth(2).inner_text()
    rows.nth(0).locator('td.check input[type="checkbox"]').check()

    admin_page.get_by_role("button", name="Générer").click()
    admin_page.wait_for_load_state("domcontentloaded")

    slip = admin_page.locator("body")
    expect(slip).to_contain_text(kept)
    expect(slip).not_to_contain_text(dropped)
