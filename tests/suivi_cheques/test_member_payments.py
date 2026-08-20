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


def test_slate_balance_links_to_where_it_is_settled(member_sheet, reseed, admin_page):
    """The link has to land on the caisse page that carries the "Rembourser"
    button. Following it for real is the point: it catches the plugin moving its
    URL, which a href-only assertion would not."""
    reseed()
    page = member_sheet()

    link = page.get_by_role("link", name="à régler à la caisse")
    expect(link).to_have_count(1)

    resp = admin_page.goto(link.first.get_attribute("href"), wait_until="domcontentloaded")
    assert resp.status == 200, f"dead link to the caisse: HTTP {resp.status}"
    expect(admin_page.locator("h1, h2").first).to_contain_text("Ardoises en cours")
    # The settle button must be there; how many debtors the fixture has is not
    # this test's business.
    expect(admin_page.get_by_role("link", name="Rembourser").first).to_be_visible()


def test_receivable_is_visible_without_any_accounting(
    member_sheet, reseed, admin_page, module_url, transaction
):
    """The debt exists as soon as the cheque is cancelled, NOT once someone has
    posted the entry. That is the whole point of the module owning the receivable:
    accounting is filled later and by hand, so making the panel depend on it would
    hide a real debt for as long as nobody clicked.

    CHQ-0142 is seeded cancelled with a partial card replacement: 45,00 paid by
    cheque, 20,00 given back by card, so 25,00 stays owed. Nothing is posted."""
    reseed()
    assert not transaction("Annulation chèque n°CHQ-0142 — Camille Martin")["found"]

    page = member_sheet(all_rows=True)
    expect(page.locator("p.help", has_text="Créance")).to_contain_text("doit 25,00")
    expect(payments_table(page).locator("tr", has_text="Créance")).to_contain_text("25,00")

    # And posting the entry does not double it: the entry is a reflection, the
    # panel reads the module either way.
    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    admin_page.locator("tr", has_text="CHQ-0142").get_by_role(
        "button", name="Comptabiliser"
    ).click()
    admin_page.wait_for_load_state("domcontentloaded")

    page = member_sheet(all_rows=True)
    expect(page.locator("p.help", has_text="Créance")).to_contain_text("doit 25,00")


def test_receivable_points_at_where_it_is_settled(member_sheet, reseed, admin_page):
    """Unlike the slate, a receivable is collected in this module — the link has to
    land on its settle page, pre-scoped to the member."""
    reseed()
    page = member_sheet()

    link = page.get_by_role("link", name="à encaisser au bureau")
    expect(link).to_have_count(1)
    resp = admin_page.goto(link.first.get_attribute("href"), wait_until="domcontentloaded")
    assert resp.status == 200, f"dead link to the settle page: HTTP {resp.status}"
    expect(admin_page.locator("h1, h2").first).to_contain_text("Camille Martin")


def test_long_history_is_capped_with_a_way_out(member_sheet, reseed):
    """The cap must never claim a truncation that did not happen, nor hide one that
    did. The seeded history is longer than the 15-row cap, so both branches show
    up here: capped by default, complete under ?all=1."""
    reseed()
    total = payments_table(member_sheet(all_rows=True)).locator("tbody tr").count()
    assert total > 15, f"fixture must exceed the cap to exercise it, got {total}"
    expect(member_sheet().locator("p.help", has_text="mouvements en tout")).to_contain_text(
        f"{total} mouvements en tout"
    )
    assert payments_table(member_sheet()).locator("tbody tr").count() == 15

    # Under ?all=1 everything is shown, so there is nothing to announce.
    page = member_sheet(all_rows=True)
    expect(page.locator("p.help", has_text="mouvements en tout")).to_have_count(0)
