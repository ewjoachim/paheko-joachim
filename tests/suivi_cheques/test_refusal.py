"""An instalment the provider (PayAsso) refused: the till kept one payment for the
whole amount, so the refused instalment becomes a receivable of the member, and
its entry credits the account the till debited for that payment.

Seeded: Camille owes 25,00 on receivables."""

from playwright.sync_api import Page, expect

MEMBER = "Camille Martin"


def owed(page: Page, module_url) -> str:
    page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")
    row = page.locator("table.list tbody tr", has_text=MEMBER)
    return row.locator("td").nth(2).inner_text().strip()


def refuse(page: Page, module_url, user, pid: int, amount: str, reason: str = "Échéance 3/10"):
    page.goto(f"{module_url}/refusal.html?user={user}", wait_until="domcontentloaded")
    page.locator('select[name="payment"]').select_option(str(pid))
    page.fill('input[name="amount"]', amount)
    page.fill('input[name="reason"]', reason)
    page.get_by_role("button", name="Enregistrer").click()
    page.wait_for_load_state("domcontentloaded")


def test_a_refused_instalment_is_owed_and_shows_on_the_member_sheet(
    admin_page: Page, module_url, reseed, seed, instalment_payment
):
    reseed()
    pid = instalment_payment(seed["camille_id"], 45000)
    refuse(admin_page, module_url, seed["camille_id"], pid, "45,00")
    expect(admin_page.locator(".confirm")).to_contain_text("doit désormais")

    assert owed(admin_page, module_url) == "70,00 €"

    admin_page.goto(f"/admin/users/details.php?id={seed['camille_id']}", wait_until="domcontentloaded")
    journal = admin_page.locator("table.list", has_text="PayAsso")
    expect(journal.locator("tr", has_text="PayAsso")).to_contain_text("Échéance refusée")
    expect(journal).to_contain_text("Créance sur échéance refusée")


def test_cheques_are_not_offered(admin_page: Page, module_url, reseed, seed, instalment_payment):
    reseed()
    pid = instalment_payment(seed["camille_id"], 45000)
    admin_page.goto(f"{module_url}/refusal.html?user={seed['camille_id']}", wait_until="domcontentloaded")
    options = admin_page.locator('select[name="payment"] option')
    expect(options).to_have_count(1)
    expect(options).to_have_attribute("value", str(pid))


def test_refusals_cannot_exceed_the_payment(admin_page: Page, module_url, reseed, seed, instalment_payment):
    reseed()
    pid = instalment_payment(seed["camille_id"], 9000)
    refuse(admin_page, module_url, seed["camille_id"], pid, "45,00")
    refuse(admin_page, module_url, seed["camille_id"], pid, "50,00", "Échéance 2/2")
    expect(admin_page.locator(".error")).to_contain_text("Il ne reste que 45,00")
    assert owed(admin_page, module_url) == "70,00 €"


def test_the_entry_credits_the_payment_account(
    admin_page: Page, module_url, reseed, seed, instalment_payment, transaction
):
    reseed()
    pid = instalment_payment(seed["camille_id"], 45000)
    refuse(admin_page, module_url, seed["camille_id"], pid, "45,00")

    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    admin_page.locator('tr:has(input[name="rec_kind"][value="refusal"])').get_by_role(
        "button", name="Comptabiliser").click()
    admin_page.wait_for_load_state("domcontentloaded")

    txn = transaction(f"Échéance PayAsso refusée — {MEMBER}")
    assert txn["found"]
    assert any(l["account"] == "512" and l["credit"] == 4500 for l in txn["lines"]), txn["lines"]
    assert any(l["account"] == "411" and l["debit"] == 4500 for l in txn["lines"]), txn["lines"]
    assert seed["camille_id"] and int(seed["camille_id"]) in txn["users"]

    admin_page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")
    expect(admin_page.locator(".alert", has_text="comptes de tiers")).to_have_count(0)


def test_a_refusal_can_be_settled_then_not_deleted(
    admin_page: Page, module_url, reseed, seed, instalment_payment
):
    reseed()
    pid = instalment_payment(seed["camille_id"], 45000)
    refuse(admin_page, module_url, seed["camille_id"], pid, "45,00")

    admin_page.goto(f"{module_url}/settle.html?user={seed['camille_id']}", wait_until="domcontentloaded")
    expect(admin_page.locator("table.list").first).to_contain_text("Échéance refusée")
    admin_page.fill('input[name="amount"]', "70,00")
    admin_page.locator('select[name="method"]').select_option(label="Espèces")
    admin_page.get_by_role("button", name="Enregistrer le règlement").click()
    admin_page.wait_for_load_state("domcontentloaded")
    # Camille still owes her slate, so her row stays, with nothing left as receivable.
    assert owed(admin_page, module_url) == "—"

    admin_page.goto(f"{module_url}/refusal.html?user={seed['camille_id']}", wait_until="domcontentloaded")
    admin_page.get_by_role("button", name="Supprimer").click()
    admin_page.wait_for_load_state("domcontentloaded")
    expect(admin_page.locator(".error")).to_contain_text("supprimez d'abord son règlement")
