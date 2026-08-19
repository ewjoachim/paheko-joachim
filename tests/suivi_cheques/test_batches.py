"""The deposit slips index (batches.html): every frozen slip, and whether its
accounting entry actually exists.

The accounting state is deliberately derived from the entry's existence, not from
the stored id alone — an accountant deleting an entry has to put the slip back in
the "to record" queue, and this page has to agree with that queue.
"""

import re

from playwright.sync_api import Page, expect


def _slip_row(page: Page):
    return page.locator("table.list tr", has_text="DEMO")


def test_lists_the_frozen_slip(admin_page: Page, module_url, reseed):
    reseed()
    admin_page.goto(f"{module_url}/batches.html", wait_until="domcontentloaded")

    row = _slip_row(admin_page)
    expect(row).to_have_count(1)
    # Seeded slip: reference DEMO, one cheque of 50,00 €.
    expect(row).to_contain_text("50,00")
    expect(row.locator("td").nth(2)).to_have_text("1")
    # Not recorded yet: the seed stores no deposit_txn_id.
    expect(row).to_contain_text("À comptabiliser")

    expect(admin_page.locator("p.help", has_text="bordereau(x)")).to_contain_text("50,00")


def test_shows_the_entry_once_recorded(
    admin_page: Page, module_url, reseed, transaction
):
    reseed()
    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    slip = admin_page.locator('form:has(input[name="rec_id"][value="DEMO"])')
    slip.get_by_role("button", name="Comptabiliser").click()
    admin_page.wait_for_load_state("domcontentloaded")

    txn = transaction("Remise de chèques n°DEMO")
    assert txn["found"], "the deposit entry should have been posted"

    admin_page.goto(f"{module_url}/batches.html", wait_until="domcontentloaded")
    row = _slip_row(admin_page)
    expect(row).to_contain_text("Comptabilisé")
    # The "!" href prefix expands to the absolute admin URL.
    expect(row.get_by_role("link", name="Voir l'écriture")).to_have_attribute(
        "href", re.compile(rf"/admin/acc/transactions/details\.php\?id={txn['id']}$")
    )


def test_falls_back_when_the_entry_was_deleted(
    admin_page: Page, module_url, reseed, purge_accounting
):
    """The slip keeps its stored deposit_txn_id, but the entry is gone: the page
    must say "à comptabiliser" again, like the queue does."""
    reseed()
    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    admin_page.locator('form:has(input[name="rec_id"][value="DEMO"])').get_by_role(
        "button", name="Comptabiliser"
    ).click()
    admin_page.wait_for_load_state("domcontentloaded")

    purge_accounting()

    admin_page.goto(f"{module_url}/batches.html", wait_until="domcontentloaded")
    row = _slip_row(admin_page)
    expect(row).to_contain_text("À comptabiliser")
    expect(row.get_by_role("link", name="Voir l'écriture")).to_have_count(0)
