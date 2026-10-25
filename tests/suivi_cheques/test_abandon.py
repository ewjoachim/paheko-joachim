"""Abandoning a debt: the board gives up on all or part of what a member owes.
No money moves; the debt shrinks, and the entry debits the account of the
reason picked (gesture 709 / bad debt 654) against the receivable account.

Seeded state: Camille Martin owes 25,00 on receivables (CHQ-0142)."""

from playwright.sync_api import Page, expect

MEMBER = "Camille Martin"


def owed(page: Page, module_url) -> str:
    page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")
    row = page.locator("table.list tbody tr", has_text=MEMBER)
    if row.count() == 0:
        return "—"
    return row.locator("td").nth(2).inner_text().strip()


def abandon(page: Page, module_url, user: str, amount: str, nature: str, reason: str):
    page.goto(f"{module_url}/settle.html?user={user}", wait_until="domcontentloaded")
    page.fill('input[name="ab_amount"]', amount)
    page.check(f'input[name="nature"][value="{nature}"]', force=True)
    page.fill('input[name="reason"]', reason)
    page.get_by_role("button", name="Abandonner").click()
    page.wait_for_load_state("domcontentloaded")


def test_partial_abandon_reduces_what_is_owed(admin_page: Page, module_url, reseed, seed):
    reseed()
    abandon(admin_page, module_url, seed["camille_id"], "10,00", "geste", "Bureau du 12/03")

    expect(admin_page.locator(".confirm")).to_contain_text("Abandon enregistré")
    expect(admin_page.locator("table.list", has_text="Bureau du 12/03")).to_contain_text("Geste accordé")
    assert owed(admin_page, module_url) == "15,00 €"


def test_abandoning_more_than_owed_is_refused(admin_page: Page, module_url, reseed, seed):
    reseed()
    abandon(admin_page, module_url, seed["camille_id"], "30,00", "impaye", "Injoignable")

    expect(admin_page.locator(".error")).to_contain_text("ne doit plus que 25,00")
    assert owed(admin_page, module_url) == "25,00 €"


def test_full_abandon_clears_the_debt_and_shows_on_the_member_sheet(
    admin_page: Page, module_url, reseed, seed
):
    reseed()
    abandon(admin_page, module_url, seed["camille_id"], "25,00", "impaye", "Injoignable")

    assert owed(admin_page, module_url) == "—"
    admin_page.goto(f"/admin/users/details.php?id={seed['camille_id']}", wait_until="domcontentloaded")
    expect(admin_page.locator("table.list", has_text="Dette abandonnée")).to_contain_text("Injoignable")


def test_abandon_is_recorded_on_the_account_of_its_reason(
    admin_page: Page, module_url, reseed, seed, transaction
):
    reseed()
    abandon(admin_page, module_url, seed["camille_id"], "25,00", "impaye", "Injoignable")

    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    row = admin_page.locator('tr:has(input[name="rec_kind"][value="abandon"])')
    expect(row).to_have_count(1)
    row.get_by_role("button", name="Comptabiliser").click()
    admin_page.wait_for_load_state("domcontentloaded")
    expect(admin_page.locator(".confirm")).to_contain_text("Écriture comptable créée")

    txn = transaction(f"Abandon de dette (impayé) — {MEMBER}")
    assert txn["found"]
    assert any(l["account"] == "654" and l["debit"] == 2500 for l in txn["lines"]), txn["lines"]
    assert any(l["account"] == "411" and l["credit"] == 2500 for l in txn["lines"]), txn["lines"]

    # Recorded on both sides: the debtors page sees no unexplained gap.
    admin_page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")
    expect(admin_page.locator(".alert", has_text="comptes de tiers")).to_have_count(0)


def test_abandon_follows_the_automatic_settlement_setting(
    admin_page: Page, module_url, reseed, seed, module_config, transaction
):
    reseed()
    module_config(auto_record_settlements=1)
    abandon(admin_page, module_url, seed["camille_id"], "25,00", "geste", "Bureau du 12/03")

    expect(admin_page.locator(".confirm", has_text="Abandon enregistré")).to_contain_text("Voir l'écriture")
    txn = transaction(f"Abandon de dette (geste accordé) — {MEMBER}")
    assert any(l["account"] == "709" and l["debit"] == 2500 for l in txn["lines"]), txn["lines"]

    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    expect(admin_page.locator('tr:has(input[name="rec_kind"][value="abandon"])')).to_have_count(0)
