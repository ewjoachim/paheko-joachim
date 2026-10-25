"""A cheque the bank sends back unpaid after the slip was deposited.

Seeded: CHQ-0143 (50,00, Camille) went to the bank on slip DEMO (2026-07-06), and
Camille owes 25,00 on receivables. A rejection reopens the debt like a
cancellation, but its entry credits the bank, not the waiting account: the
deposit entry already took the cheque out of 5112."""

from playwright.sync_api import Page, expect

MEMBER = "Camille Martin"


def chq_0143(seed) -> int:
    # seed-demo.php inserts CHQ-0140..0148 in order.
    return int(seed["pay_edit"]) + 3


def reject(page: Page, module_url, pid: int, reason: str = "Sans provision"):
    page.goto(f"{module_url}/edit.html?payment={pid}", wait_until="domcontentloaded")
    page.check('input[name="cancelled"]', force=True)
    page.fill('input[name="reason"]', reason)
    page.get_by_role("button", name="Enregistrer").click()
    page.wait_for_load_state("domcontentloaded")


def owed(page: Page, module_url) -> str:
    page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")
    row = page.locator("table.list tbody tr", has_text=MEMBER)
    return row.locator("td").nth(2).inner_text().strip()


def test_a_deposited_cheque_only_offers_the_rejection(admin_page: Page, module_url, reseed, seed):
    reseed()
    admin_page.goto(f"{module_url}/edit.html?payment={chq_0143(seed)}", wait_until="domcontentloaded")
    expect(admin_page.get_by_text("Rejeté par la banque").first).to_be_visible()
    expect(admin_page.locator('input[name="cheque_number"]')).to_have_count(0)
    expect(admin_page.locator('select[name="planned_month"]')).to_have_count(0)


def test_a_rejection_reopens_the_debt_and_credits_the_bank(
    admin_page: Page, module_url, reseed, seed, transaction
):
    reseed()
    reject(admin_page, module_url, chq_0143(seed))

    assert owed(admin_page, module_url) == "75,00 €"
    admin_page.goto(f"{module_url}/index.html?period=2026-07&state=cancelled", wait_until="domcontentloaded")
    expect(admin_page.locator("#cheques tr", has_text="CHQ-0143")).to_contain_text("Rejeté")

    # The slip itself is untouched: the cheque did go to the bank.
    admin_page.goto(f"{module_url}/batch.html?batch=DEMO", wait_until="domcontentloaded")
    expect(admin_page.locator("table.list")).to_contain_text("CHQ-0143")

    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    row = admin_page.locator('tr:has(input[name="rec_kind"][value="annul_pay"])', has_text="CHQ-0143")
    expect(row).to_contain_text("Rejeté")
    row.get_by_role("button", name="Comptabiliser").click()
    admin_page.wait_for_load_state("domcontentloaded")

    txn = transaction(f"Rejet chèque n°CHQ-0143 — {MEMBER}")
    assert txn["found"]
    assert any(l["account"] == "512" and l["credit"] == 5000 for l in txn["lines"]), txn["lines"]
    assert any(l["account"] == "411" and l["debit"] == 5000 for l in txn["lines"]), txn["lines"]
    assert not any(l["account"] == "5112" for l in txn["lines"]), txn["lines"]


def test_a_slip_with_a_rejected_cheque_cannot_be_cancelled(admin_page: Page, module_url, reseed, seed):
    reseed()
    reject(admin_page, module_url, chq_0143(seed))

    admin_page.on("dialog", lambda d: d.accept())
    admin_page.goto(f"{module_url}/batch.html?batch=DEMO", wait_until="domcontentloaded")
    admin_page.get_by_role("button", name="Annuler le bordereau").click()
    admin_page.wait_for_load_state("domcontentloaded")
    expect(admin_page.locator(".error")).to_contain_text("rejeté par la banque")


def test_a_cheque_on_an_open_slip_stays_locked(admin_page: Page, module_url, reseed, seed, add_to_slip):
    reseed()
    pid = int(seed["pay_edit"])
    admin_page.goto(f"{module_url}/index.html?period=2026-07&state=todo", wait_until="domcontentloaded")
    admin_page.check(f'input[name="deposit[pay-{pid}]"]', force=True)
    add_to_slip(admin_page)

    admin_page.goto(f"{module_url}/edit.html?payment={pid}", wait_until="domcontentloaded")
    expect(admin_page.locator(".confirm")).to_contain_text("bordereau en cours")
    expect(admin_page.locator('input[name="cancelled"]')).to_have_count(0)
