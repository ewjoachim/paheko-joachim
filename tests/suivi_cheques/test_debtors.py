"""Debtors page: who owes money, from the two sources that can produce a debt.

The slate lives only in the till tables; the receivable only in accounting, and
only for entries explicitly linked to a member. The page keeps them in separate
columns because they are settled in different places.
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

    # Camille owes on both sides (40,00 slate + 25,00 receivable once posted is
    # tested below); Sofia owes 60,00 on the slate only — so with no receivable
    # posted yet, Sofia's 60,00 outranks Camille's 40,00.
    expect(rows.nth(0)).to_contain_text("Sofia Nkemelu")
    expect(rows.nth(1)).to_contain_text("Camille Martin")


def test_the_two_debts_stay_in_separate_columns(admin_page: Page, module_url, reseed):
    """Sofia owes on the slate and nothing in accounting: her receivable cell must
    be empty, not a zero folded into a single net figure."""
    reseed()
    admin_page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")

    cells = row(admin_page, "Sofia Nkemelu").locator("td")
    assert cells.nth(1).inner_text().strip() == "60,00 €", "slate column"
    assert cells.nth(2).inner_text().strip() == "—", "receivable column must stay empty"
    assert cells.nth(3).inner_text().strip() == "60,00 €", "total"


def test_receivable_shows_up_and_adds_to_the_total(
    admin_page: Page, module_url, reseed
):
    """Posting the cancellation of CHQ-0142 gives Camille a 25,00 receivable on top
    of her 40,00 slate — the only case where one member owes on both sides."""
    reseed()
    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    admin_page.locator("tr", has_text="CHQ-0142").get_by_role(
        "button", name="Comptabiliser"
    ).click()
    admin_page.wait_for_load_state("domcontentloaded")

    admin_page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")
    cells = row(admin_page, "Camille Martin").locator("td")
    assert cells.nth(1).inner_text().strip() == "40,00 €", "slate"
    assert cells.nth(2).inner_text().strip() == "25,00 €", "receivable"
    assert cells.nth(3).inner_text().strip() == "65,00 €", "total"

    # Camille now outranks Sofia, and the footer totals both columns.
    expect(admin_page.locator("table.list tbody tr").nth(0)).to_contain_text("Camille")
    foot = admin_page.locator("tfoot tr")
    expect(foot).to_contain_text("100,00 €")  # slate: 40 + 60
    expect(foot).to_contain_text("25,00 €")  # receivable
    expect(foot).to_contain_text("125,00 €")  # grand total


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
