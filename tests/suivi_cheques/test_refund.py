"""Refunding a member, in two steps: the board decides (the association now owes
the money, visible at once), then the money leaves (only then is there an
accounting entry: debit gesture 709, credit the account it left from)."""

from playwright.sync_api import Page, expect

MEMBER = "Camille Martin"


def decide(page: Page, module_url, user: str, amount: str, reason: str):
    page.goto(f"{module_url}/refund.html?user={user}", wait_until="domcontentloaded")
    page.fill('input[name="amount"]', amount)
    page.fill('input[name="reason"]', reason)
    page.get_by_role("button", name="Enregistrer").click()
    page.wait_for_load_state("domcontentloaded")


def pay(page: Page, module_url, user: str, means: str = "Virement ou chèque de l'association"):
    page.goto(f"{module_url}/refund.html?user={user}", wait_until="domcontentloaded")
    page.locator('select[name="means"]').select_option(label=means)
    page.get_by_role("button", name="Marquer comme remboursé").click()
    page.wait_for_load_state("domcontentloaded")


def owed_by_us(page: Page, module_url):
    page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")
    return page.locator("table.list:has(th:text('À rembourser')) tbody tr", has_text=MEMBER)


def queue_row(page: Page, module_url):
    page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    return page.locator('tr:has(input[name="rec_kind"][value="refund"])')


def test_a_decided_refund_is_owed_before_any_entry(admin_page: Page, module_url, reseed, seed):
    reseed()
    decide(admin_page, module_url, seed["camille_id"], "120,00", "Bureau du 12/03, déménagement")
    expect(admin_page.locator(".confirm")).to_contain_text("à rembourser")

    expect(owed_by_us(admin_page, module_url)).to_contain_text("120,00")
    expect(queue_row(admin_page, module_url)).to_have_count(0)

    admin_page.goto(f"/admin/users/details.php?id={seed['camille_id']}", wait_until="domcontentloaded")
    expect(admin_page.get_by_text("l'association lui doit")).to_contain_text("120,00")


def test_paying_it_queues_the_entry(admin_page: Page, module_url, reseed, seed, transaction):
    reseed()
    decide(admin_page, module_url, seed["camille_id"], "120,00", "Bureau du 12/03")
    pay(admin_page, module_url, seed["camille_id"])
    expect(admin_page.locator("table.list")).to_contain_text("Remboursé")

    expect(owed_by_us(admin_page, module_url)).to_have_count(0)
    row = queue_row(admin_page, module_url)
    expect(row).to_have_count(1)
    row.get_by_role("button", name="Comptabiliser").click()
    admin_page.wait_for_load_state("domcontentloaded")

    txn = transaction(f"Remboursement — {MEMBER}")
    assert txn["found"]
    assert any(l["account"] == "709" and l["debit"] == 12000 for l in txn["lines"]), txn["lines"]
    assert any(l["account"] == "512" and l["credit"] == 12000 for l in txn["lines"]), txn["lines"]

    # Recorded: it can no longer be deleted from the module.
    admin_page.goto(f"{module_url}/refund.html?user={seed['camille_id']}", wait_until="domcontentloaded")
    expect(admin_page.get_by_role("button", name="Supprimer")).to_have_count(0)


def test_a_pending_refund_can_be_deleted(admin_page: Page, module_url, reseed, seed):
    reseed()
    decide(admin_page, module_url, seed["camille_id"], "50,00", "Erreur")
    admin_page.get_by_role("button", name="Supprimer").click()
    admin_page.wait_for_load_state("domcontentloaded")

    expect(admin_page.locator(".confirm")).to_contain_text("supprimé")
    expect(owed_by_us(admin_page, module_url)).to_have_count(0)


def test_refund_follows_the_automatic_setting(
    admin_page: Page, module_url, reseed, seed, module_config, transaction
):
    reseed()
    module_config(auto_record_settlements=1)
    decide(admin_page, module_url, seed["camille_id"], "80,00", "Bureau du 12/03")
    pay(admin_page, module_url, seed["camille_id"])

    expect(admin_page.locator(".confirm")).to_contain_text("Voir l'écriture")
    assert transaction(f"Remboursement — {MEMBER}")["found"]
    expect(queue_row(admin_page, module_url)).to_have_count(0)
