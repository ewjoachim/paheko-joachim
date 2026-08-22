"""A deposit slip lives in three states: en cours, déposé, comptabilisé.

What separates the first two is a physical fact — someone walked to the bank —
and the module records it as a date. Everything else follows from that date:
a slip without one can still be changed, is not printable, and has nothing to
record; a slip with one is frozen.
"""

import re

from playwright.sync_api import Page, expect

JULY = "index.html?period=2026-07&state=%s"
SEPT = "index.html?period=2026-09&state=todo"


def _tick_all_and_add(page, module_url, view, add_to_slip):
    page.goto(f"{module_url}/{view}", wait_until="domcontentloaded")
    page.get_by_role("button", name="Tout cocher").click()
    add_to_slip(page)
    return re.search(r"[?&]batch=([^&]+)", page.url).group(1)


def test_a_new_slip_is_open_and_has_nothing_to_record(
    admin_page: Page, module_url, reseed, add_to_slip
):
    reseed()
    ref = _tick_all_and_add(admin_page, module_url, JULY % "todo", add_to_slip)

    expect(admin_page.get_by_text("En cours")).to_have_count(1)
    expect(admin_page.get_by_role("button", name="Marquer comme déposé")).to_have_count(1)
    # Nothing to print and nothing to record: it has not left the building.
    expect(admin_page.get_by_role("button", name="Imprimer")).to_have_count(0)

    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    expect(admin_page.locator(f'form:has(input[name="rec_id"][value="{ref}"])')).to_have_count(0)


def test_the_trip_to_the_bank_freezes_it_and_queues_it(
    admin_page: Page, module_url, reseed, add_to_slip, take_to_bank
):
    reseed()
    _tick_all_and_add(admin_page, module_url, JULY % "todo", add_to_slip)
    ref = take_to_bank(admin_page)

    expect(admin_page.get_by_role("button", name="Retirer")).to_have_count(0)
    expect(admin_page.get_by_role("button", name="Marquer comme déposé")).to_have_count(0)
    expect(admin_page.get_by_role("button", name="Imprimer")).to_have_count(1)

    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    expect(admin_page.locator(f'form:has(input[name="rec_id"][value="{ref}"])')).to_have_count(1)


def test_a_cheque_in_an_open_slip_is_in_a_lot_not_deposited(
    admin_page: Page, module_url, reseed, add_to_slip, take_to_bank
):
    """The distinction the four chips exist for: a cheque in an open slip is still
    on the desk, and only the trip to the bank makes it gone."""
    reseed()
    _tick_all_and_add(admin_page, module_url, JULY % "todo", add_to_slip)

    admin_page.goto(f"{module_url}/{JULY % 'all'}", wait_until="domcontentloaded")
    expect(admin_page.locator("p.actions a", has_text="Dans un lot")).to_contain_text("Dans un lot (1)")
    row = admin_page.locator("table.list tbody tr", has_text="CHQ-0140")
    expect(row).to_contain_text("Dans un lot")

    admin_page.goto(f"{module_url}/batches.html", wait_until="domcontentloaded")
    admin_page.get_by_role("link", name=re.compile(r"^\d{8}-")).first.click()
    admin_page.wait_for_load_state("domcontentloaded")
    take_to_bank(admin_page)

    admin_page.goto(f"{module_url}/{JULY % 'all'}", wait_until="domcontentloaded")
    expect(admin_page.locator("p.actions a", has_text="Dans un lot")).to_contain_text("Dans un lot (0)")
    expect(admin_page.locator("p.actions a", has_text="Déposé")).to_contain_text("Déposé (2)")


def test_removing_a_cheque_returns_it_to_the_view(
    admin_page: Page, module_url, reseed, add_to_slip
):
    reseed()
    _tick_all_and_add(admin_page, module_url, JULY % "todo", add_to_slip)

    admin_page.get_by_role("button", name="Retirer").first.click()
    admin_page.wait_for_load_state("domcontentloaded")
    expect(admin_page.locator(".confirm")).to_contain_text("repassé")

    admin_page.goto(f"{module_url}/{JULY % 'todo'}", wait_until="domcontentloaded")
    expect(admin_page.locator("table.list tbody tr", has_text="CHQ-0140")).to_have_count(1)


def test_a_second_batch_of_cheques_joins_the_open_slip(
    admin_page: Page, module_url, reseed, add_to_slip
):
    """One trip to the bank, one slip: the pile in progress is preselected, so
    ticking a second month adds to it rather than opening a rival slip."""
    reseed()
    ref = _tick_all_and_add(admin_page, module_url, JULY % "todo", add_to_slip)

    admin_page.goto(f"{module_url}/{SEPT}", wait_until="domcontentloaded")
    target = admin_page.locator('select[name="target"]')
    assert target.input_value() == ref, "the slip in progress should be the default"

    admin_page.get_by_role("button", name="Tout cocher").click()
    add_to_slip(admin_page)

    assert ref in admin_page.url, "the cheques went into a different slip"
    # One from July, two from September.
    expect(admin_page.locator("table.list tbody tr")).to_have_count(3 + 1)  # + the total row

    admin_page.goto(f"{module_url}/batches.html", wait_until="domcontentloaded")
    expect(admin_page.locator("table.list tbody tr", has_text=ref)).to_have_count(1)


def test_a_new_slip_can_still_be_opened_alongside(
    admin_page: Page, module_url, reseed, add_to_slip
):
    reseed()
    first = _tick_all_and_add(admin_page, module_url, JULY % "todo", add_to_slip)

    admin_page.goto(f"{module_url}/{SEPT}", wait_until="domcontentloaded")
    admin_page.select_option('select[name="target"]', "new")
    admin_page.get_by_role("button", name="Tout cocher").click()
    add_to_slip(admin_page)

    second = re.search(r"[?&]batch=([^&]+)", admin_page.url).group(1)
    assert second != first
    expect(admin_page.get_by_text("En cours")).to_have_count(1)


def test_an_open_slip_can_be_ticked_off_for_a_recount(
    admin_page: Page, module_url, reseed, add_to_slip
):
    """Scratch checkboxes: they carry no name, so they never reach the POST — they
    exist to walk down the pile without losing the count."""
    reseed()
    _tick_all_and_add(admin_page, module_url, SEPT, add_to_slip)

    boxes = admin_page.locator('#slip tbody input[type="checkbox"]')
    expect(boxes).to_have_count(2)
    assert boxes.first.get_attribute("name") is None, "a recount box must not be submitted"

    boxes.first.check()
    expect(admin_page.locator("#recount")).to_contain_text("Pointés : 1 / 2")
    boxes.nth(1).check()
    expect(admin_page.locator("#recount")).to_contain_text("2 / 2")
    expect(admin_page.locator("#recount")).to_contain_text("75,00")


def test_a_slip_exports_only_its_own_cheques(
    admin_page: Page, module_url, reseed, add_to_slip
):
    reseed()
    _tick_all_and_add(admin_page, module_url, SEPT, add_to_slip)

    admin_page.get_by_text("Exporter", exact=True).click()
    with admin_page.expect_download() as caught:
        admin_page.get_by_role("link", name="Export CSV").click()
    body = caught.value.path().read_text(encoding="utf-8")

    assert "CHQ-0145" in body and "CHQ-0200" in body
    # CHQ-0140 is July's, and never joined this slip.
    assert "CHQ-0140" not in body
    assert body.splitlines()[0].startswith('"N° de chèque"')


def test_an_unknown_slip_does_not_export(admin_page: Page, module_url, reseed):
    """The reference reaches the SQL API as text, so it is looked up first and only
    what the database hands back is used."""
    reseed()
    admin_page.goto(
        f"{module_url}/export.html?batch=nope&format=csv", wait_until="domcontentloaded"
    )
    expect(admin_page.locator(".block.error")).to_contain_text("introuvable")
