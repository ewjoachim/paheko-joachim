"""Picking the cheques that go into a deposit slip, from the single view.

The checkbox has to be *visible*: Paheko hides the real <input> (opacity: 0) and
draws the box through a sibling <label>, inside a `<td class="check">`. A bare
<input> in a plain <td> is present, submits, and passes every functional test —
while showing nothing on screen. Hence the computed-opacity assertion below:
Playwright's is_visible() ignores opacity and reports such a checkbox as visible.

Filtering and sorting are the other half: they run in the browser precisely so
that they never lose a tick, which is what the last two tests pin down.
"""

from playwright.sync_api import Page, expect

MONTH = "2026-09"  # 2 eligible cheques in the demo fixture
VIEW = "index.html?period=%s&state=%s"
BOXES = 'table.list tbody td.check input[type="checkbox"][name^="deposit["]'


def test_checkbox_is_actually_drawn(admin_page: Page, module_url, reseed):
    reseed()
    admin_page.goto(f"{module_url}/{VIEW % (MONTH, 'todo')}", wait_until="domcontentloaded")

    boxes = admin_page.locator(BOXES)
    expect(boxes).to_have_count(2)

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
    admin_page.goto(f"{module_url}/{VIEW % (MONTH, 'todo')}", wait_until="domcontentloaded")
    expect(admin_page.locator(f"{BOXES}:checked")).to_have_count(0)

    # Generating without ticking anything freezes nothing and says so.
    admin_page.get_by_role("button", name="Ajouter au bordereau").click()
    admin_page.wait_for_load_state("domcontentloaded")
    expect(admin_page.locator(".error")).to_contain_text("Aucun chèque éligible sélectionné")


def test_a_non_depositable_cheque_keeps_a_greyed_box(admin_page: Page, module_url, reseed):
    """The box stays in place on a cancelled or already-deposited row: the columns
    line up, and the state of a row reads without scanning it."""
    reseed()
    admin_page.goto(f"{module_url}/{VIEW % ('2026-07', 'all')}", wait_until="domcontentloaded")

    row = admin_page.locator("table.list tbody tr", has_text="CHQ-0143")  # in the DEMO slip
    expect(row).to_have_count(1)
    box = row.locator('td.check input[type="checkbox"]')
    expect(box).to_have_count(1)
    assert box.is_disabled(), "an already-deposited cheque must not be tickable"
    assert box.get_attribute("name") is None, "and must not be submitted"


def test_check_all_only_takes_what_the_filter_shows(admin_page: Page, module_url, reseed):
    reseed()
    admin_page.goto(f"{module_url}/{VIEW % (MONTH, 'todo')}", wait_until="domcontentloaded")

    target = admin_page.locator("table.list tbody tr").first
    number = target.locator("td").nth(1).inner_text().strip()

    admin_page.fill("#cheques-filter", number)
    admin_page.get_by_role("button", name="Tout cocher").click()
    expect(admin_page.locator(f"{BOXES}:checked")).to_have_count(1)

    # Emptying the filter brings the others back — still unticked, and the one
    # ticked through the filter is still ticked.
    admin_page.fill("#cheques-filter", "")
    expect(admin_page.locator(f"{BOXES}:checked")).to_have_count(1)
    expect(admin_page.locator(BOXES)).to_have_count(2)


def test_filtering_and_sorting_never_untick(admin_page: Page, module_url, reseed):
    """The real gesture: hold the pile, type a number, tick, clear, next. A server
    round-trip would lose the ticks, so both run in the browser."""
    reseed()
    # Every month at once: enough rows for sorting to actually move them around.
    admin_page.goto(f"{module_url}/{VIEW % ('all', 'todo')}", wait_until="domcontentloaded")

    boxes = admin_page.locator(BOXES)
    boxes.nth(0).check()
    boxes.nth(2).check()

    admin_page.fill("#cheques-filter", "zzz-nothing-matches")
    admin_page.fill("#cheques-filter", "")
    admin_page.click('table.list thead th[data-key="amount"]')
    admin_page.click('table.list thead th[data-key="member"]')

    expect(admin_page.locator(f"{BOXES}:checked")).to_have_count(2)
    # And the live counter agrees with what is ticked.
    expect(admin_page.locator("#cheques-selection")).to_contain_text("2 coché")


def test_only_ticked_cheques_go_into_the_slip(admin_page: Page, module_url, reseed):
    reseed()
    admin_page.goto(f"{module_url}/{VIEW % (MONTH, 'todo')}", wait_until="domcontentloaded")

    rows = admin_page.locator("table.list tbody tr")
    kept = rows.nth(0).locator("td").nth(1).inner_text()
    dropped = rows.nth(1).locator("td").nth(1).inner_text()
    rows.nth(0).locator('td.check input[type="checkbox"]').check()

    admin_page.get_by_role("button", name="Ajouter au bordereau").click()
    admin_page.wait_for_load_state("domcontentloaded")

    slip = admin_page.locator("body")
    expect(slip).to_contain_text(kept)
    expect(slip).not_to_contain_text(dropped)
