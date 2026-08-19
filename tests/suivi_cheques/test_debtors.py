"""Debtors page: who owes money, from the two sources that can produce a debt.

Each debt is read from the tool that owns it: the slate from the till tables, the
receivable from this module's own documents. Neither is read from accounting,
which only mirrors them. The page keeps them in separate columns because they are
settled in different places.
"""

from playwright.sync_api import Page, expect


def row(page: Page, name: str):
    return page.locator("table.list tbody tr", has_text=name)


def test_lists_both_debtors_biggest_first(admin_page: Page, module_url, reseed):
    reseed()
    admin_page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")
    assert admin_page.locator(".exception, .error").count() == 0

    # Only the two seeded debtors: nobody who owes nothing may show up here.
    rows = admin_page.locator("table.list tbody tr")
    expect(rows).to_have_count(2)

    # Camille owes on both sides (40,00 slate + 25,00 receivable), Sofia 60,00 on
    # the slate only — and Camille's receivable counts from the start, without
    # anything being posted to accounting.
    expect(rows.nth(0)).to_contain_text("Camille Martin")
    expect(rows.nth(1)).to_contain_text("Sofia Nkemelu")


def test_the_two_debts_stay_in_separate_columns(admin_page: Page, module_url, reseed):
    """Sofia owes on the slate and nothing in accounting: her receivable cell must
    be empty, not a zero folded into a single net figure."""
    reseed()
    admin_page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")

    cells = row(admin_page, "Sofia Nkemelu").locator("td")
    assert cells.nth(1).inner_text().strip() == "60,00 €", "slate column"
    assert cells.nth(2).inner_text().strip() == "—", "receivable column must stay empty"
    assert cells.nth(3).inner_text().strip() == "60,00 €", "total"


def test_receivable_counts_before_any_accounting(
    admin_page: Page, module_url, reseed, purge_accounting
):
    """The 25,00 CHQ-0142 left uncovered shows up with nothing posted at all — the
    reason the module owns receivables instead of reading them back from entries
    that a human fills in later, and might fill in without linking the member."""
    reseed()
    purge_accounting()

    admin_page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")
    cells = row(admin_page, "Camille Martin").locator("td")
    assert cells.nth(1).inner_text().strip() == "40,00 €", "slate"
    assert cells.nth(2).inner_text().strip() == "25,00 €", "receivable"
    assert cells.nth(3).inner_text().strip() == "65,00 €", "total"

    foot = admin_page.locator("tfoot tr")
    expect(foot).to_contain_text("100,00 €")  # slate: 40 + 60
    expect(foot).to_contain_text("25,00 €")  # receivable
    expect(foot).to_contain_text("125,00 €")  # grand total


def test_settling_the_receivable_clears_the_column(
    admin_page: Page, module_url, reseed, transaction
):
    """Collecting the money is an operation of this module: the column drops, and
    the entry it produces links the member — the link a hand-typed entry is free to
    omit."""
    reseed()
    admin_page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")
    row(admin_page, "Camille Martin").get_by_role("link", name="Régler la créance").click()
    admin_page.wait_for_load_state("domcontentloaded")

    admin_page.locator('select[name="method"]').select_option(label="Espèces")
    admin_page.get_by_role("button", name="Enregistrer le règlement").click()
    admin_page.wait_for_load_state("domcontentloaded")
    # Two confirmations now: the settlement, and "nothing left owed".
    expect(admin_page.locator(".block.confirm").first).to_contain_text("Règlement enregistré")
    expect(admin_page.locator(".block.confirm").last).to_contain_text("ne doit plus rien")

    # Camille keeps her slate but owes nothing on the receivable side any more.
    admin_page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")
    cells = row(admin_page, "Camille Martin").locator("td")
    assert cells.nth(2).inner_text().strip() == "—", "receivable column must clear"
    assert cells.nth(3).inner_text().strip() == "40,00 €", "only the slate is left"

    # The entry waits in the queue (automatic recording is off by default).
    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    expect(
        admin_page.locator("table.list", has_text="CHQ-0142").locator(
            "tr", has_text="25,00"
        ).first
    ).to_be_visible()


def test_slate_row_offers_a_way_to_settle(admin_page: Page, module_url, reseed):
    reseed()
    admin_page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")

    link = row(admin_page, "Sofia Nkemelu").get_by_role("link", name="Régler l'ardoise")
    expect(link).to_have_count(1)
    resp = admin_page.goto(link.get_attribute("href"), wait_until="domcontentloaded")
    assert resp.status == 200, f"dead link to the caisse: HTTP {resp.status}"
    expect(admin_page.locator("h1, h2").first).to_contain_text("Ardoises en cours")


def test_unattached_slate_debt_is_announced_not_swallowed(
    admin_page: Page, module_url, reseed, orphan_slate_debt
):
    """A slate taken on a tab with no member cannot appear in a per-member list.
    Staying silent would make the page's total understate what is owed."""
    reseed()
    admin_page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")
    expect(admin_page.locator(".block.alert")).to_have_count(0)

    orphan_slate_debt(1500)
    admin_page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")

    warning = admin_page.locator(".block.alert")
    expect(warning).to_contain_text("15,00 €")
    expect(warning).to_contain_text("aucune fiche membre")
    # It is not silently folded into the per-member rows either.
    expect(admin_page.locator("table.list tbody tr")).to_have_count(2)
