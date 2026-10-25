"""Refunding a member: recorded once the money has left, in one step. One refund,
one entry: debit gesture 709, credit the account the money left from."""

from playwright.sync_api import Page, expect

MEMBER = "Camille Martin"


def refund(page: Page, module_url, user: str, amount: str, reason: str,
           means: str = "Virement ou chèque de l'association"):
    page.goto(f"{module_url}/refund.html?user={user}", wait_until="domcontentloaded")
    page.fill('input[name="amount"]', amount)
    page.fill('input[name="reason"]', reason)
    page.locator('select[name="means"]').select_option(label=means)
    page.get_by_role("button", name="Enregistrer le remboursement").click()
    page.wait_for_load_state("domcontentloaded")


def queue_row(page: Page, module_url):
    page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    return page.locator('tr:has(input[name="rec_kind"][value="refund"])')


def test_a_refund_is_one_entry_on_the_bank(admin_page: Page, module_url, reseed, seed, transaction):
    reseed()
    refund(admin_page, module_url, seed["camille_id"], "120,00", "Bureau du 12/03, déménagement")
    expect(admin_page.locator(".confirm")).to_contain_text("Remboursement enregistré")

    admin_page.goto(f"/admin/users/details.php?id={seed['camille_id']}", wait_until="domcontentloaded")
    expect(admin_page.locator("table.list", has_text="Remboursement")).to_contain_text("déménagement")

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


def test_an_unrecorded_refund_can_be_deleted(admin_page: Page, module_url, reseed, seed):
    reseed()
    refund(admin_page, module_url, seed["camille_id"], "50,00", "Erreur")
    admin_page.get_by_role("button", name="Supprimer").click()
    admin_page.wait_for_load_state("domcontentloaded")

    expect(admin_page.locator(".confirm")).to_contain_text("supprimé")
    expect(queue_row(admin_page, module_url)).to_have_count(0)


def test_refund_follows_the_automatic_setting(
    admin_page: Page, module_url, reseed, seed, module_config, transaction
):
    reseed()
    module_config(auto_record_settlements=1)
    refund(admin_page, module_url, seed["camille_id"], "80,00", "Bureau du 12/03")

    expect(admin_page.locator(".confirm")).to_contain_text("Voir l'écriture")
    assert transaction(f"Remboursement — {MEMBER}")["found"]
    expect(queue_row(admin_page, module_url)).to_have_count(0)
