"""Member sheet: the payments panel unions every source of money for a member.

The panel is a journal, not a ledger: one Montant column, the Type column carries
the meaning. The two debts (slate, receivable) are shown as separate balances
because they settle differently and their sign conventions are opposite.
"""

from playwright.sync_api import Page, expect

import pytest


@pytest.fixture
def member_sheet(admin_page: Page, module_url, seed):
    """Open the seeded member's sheet and return the payments table locator."""

    def _open(all_rows: bool = False) -> Page:
        base = module_url.split("/m/")[0]
        url = f"{base}/admin/users/details.php?id={seed['camille_id']}"
        if all_rows:
            url += "&all=1"
        admin_page.goto(url, wait_until="domcontentloaded")
        assert admin_page.locator(".exception").count() == 0, "template error on the member sheet"
        return admin_page

    return _open


def payments_table(page: Page):
    return page.locator("table.list").filter(has=page.get_by_role("columnheader", name="Libellé"))


def test_panel_unions_every_source(member_sheet, reseed):
    reseed()
    page = member_sheet(all_rows=True)

    expect(page.locator("h2", has_text="Paiements")).to_have_count(1)
    table = payments_table(page)

    # A till purchase (tabs_items), which the old cheques-only panel never showed.
    expect(table.locator("tr", has_text="Cours de guitare")).to_have_count(1)
    # A tracked cheque, with its module state.
    row = table.locator("tr", has_text="CHQ-0140")
    expect(row).to_contain_text("Chèque")
    expect(row).to_contain_text("À encaisser")
    # A cash payment: a type the panel could not show before either.
    expect(table.locator("tr", has_text="Espèces")).to_have_count(1)
    # A replacement cheque, tracked by the module and never seen by the till.
    expect(table.locator("tr", has_text="CHQ-0200")).to_contain_text("Remplacement")


def test_slate_is_not_counted_as_a_payment(member_sheet, reseed):
    """A slate payment defers the debt, it does not settle it — so it gets its own
    tag in the journal and drives the slate balance."""
    reseed()
    page = member_sheet(all_rows=True)

    expect(page.locator("p.help", has_text="Ardoise")).to_contain_text("doit 40,00")
    expect(payments_table(page).locator("tr", has_text="Ardoise")).to_contain_text("Porté en ardoise")


def test_cancelled_cheque_shows_up_as_a_receivable(
    member_sheet, reseed, admin_page, module_url
):
    """The receivable only exists once the cancellation is posted to accounting.
    That is the second way a member ends up owing money, and the only one
    accounting can attribute to them."""
    reseed()

    # CHQ-0142 is seeded cancelled with a partial card replacement: 45,00 paid by
    # cheque, 20,00 given back by card, so 25,00 stays a receivable. Post THAT row
    # — CHQ-0141 is replaced by another cheque in full and leaves no receivable.
    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    row = admin_page.locator("tr", has_text="CHQ-0142")
    row.get_by_role("button", name="Comptabiliser").click()
    admin_page.wait_for_load_state("domcontentloaded")

    page = member_sheet(all_rows=True)
    expect(page.locator("p.help", has_text="Créance")).to_contain_text("doit 25,00")
    expect(payments_table(page).locator("tr", has_text="Créance")).to_contain_text("25,00")


def test_long_history_is_capped_with_a_way_out(member_sheet, reseed):
    """15 movements are seeded, so the default view shows them all and says
    nothing; ?all=1 must not claim a truncation that did not happen."""
    reseed()
    page = member_sheet()
    rows = payments_table(page).locator("tbody tr").count()
    assert rows == 15, f"expected the 15 seeded movements, got {rows}"
    expect(page.locator("p.help", has_text="mouvements en tout")).to_have_count(0)
