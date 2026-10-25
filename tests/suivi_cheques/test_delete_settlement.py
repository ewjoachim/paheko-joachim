"""A settlement or an abandon typed by mistake can be deleted from the settle page
while its entry does not exist. The member then owes the amount again.

Seeded state: Camille owes 25,00 (CHQ-0142 45,00, settled 20,00 in cash by
regl-demo-0142), and CHQ-0141 was settled in full by cheque CHQ-0200
(regl-demo-0200)."""

from playwright.sync_api import Page, expect

MEMBER = "Camille Martin"


def owed(page: Page, module_url) -> str:
    page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")
    row = page.locator("table.list tbody tr", has_text=MEMBER)
    return row.locator("td").nth(2).inner_text().strip() if row.count() else "—"


def delete_row(page: Page, module_url, user: str, key: str):
    page.on("dialog", lambda d: d.accept())
    page.goto(f"{module_url}/settle.html?user={user}", wait_until="domcontentloaded")
    page.locator(f'form:has(input[name="del_key"][value="{key}"])').get_by_role("button", name="Supprimer").click()
    page.wait_for_load_state("domcontentloaded")


def test_deleting_a_settlement_makes_the_amount_due_again(admin_page: Page, module_url, reseed, seed):
    reseed()
    delete_row(admin_page, module_url, seed["camille_id"], "regl-demo-0142")
    expect(admin_page.locator(".confirm")).to_contain_text("de nouveau due")
    assert owed(admin_page, module_url) == "45,00 €"


def test_deleting_a_settlement_by_cheque_takes_the_cheque_with_it(admin_page: Page, module_url, reseed, seed):
    reseed()
    delete_row(admin_page, module_url, seed["camille_id"], "regl-demo-0200")
    assert owed(admin_page, module_url) == "55,00 €"
    admin_page.goto(f"{module_url}/index.html?period=all&state=all", wait_until="domcontentloaded")
    expect(admin_page.locator("#cheques tr", has_text="CHQ-0200")).to_have_count(0)


def test_a_settlement_cheque_already_on_a_slip_blocks_the_delete(
    admin_page: Page, module_url, reseed, seed, add_to_slip
):
    reseed()
    admin_page.goto(f"{module_url}/index.html?period=2026-09&state=todo", wait_until="domcontentloaded")
    admin_page.check('input[name="deposit[chq-regl-demo-0200]"]', force=True)
    add_to_slip(admin_page)

    delete_row(admin_page, module_url, seed["camille_id"], "regl-demo-0200")
    expect(admin_page.locator(".error")).to_contain_text("bordereau")
    assert owed(admin_page, module_url) == "25,00 €"


def test_a_recorded_settlement_cannot_be_deleted(admin_page: Page, module_url, reseed, seed):
    reseed()
    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    admin_page.locator('tr:has(input[name="rec_kind"][value="settlement"])', has_text="20,00").get_by_role(
        "button", name="Comptabiliser").click()
    admin_page.wait_for_load_state("domcontentloaded")

    admin_page.goto(f"{module_url}/settle.html?user={seed['camille_id']}", wait_until="domcontentloaded")
    expect(admin_page.locator('input[name="del_key"][value="regl-demo-0142"]')).to_have_count(0)
    expect(admin_page.locator('input[name="del_key"][value="regl-demo-0200"]')).to_have_count(1)


def test_history_stays_visible_once_the_debt_is_cleared(admin_page: Page, module_url, reseed, seed):
    """Otherwise a settlement that cleared the whole debt could never be deleted."""
    reseed()
    admin_page.goto(f"{module_url}/settle.html?user={seed['camille_id']}", wait_until="domcontentloaded")
    admin_page.fill('input[name="ab_amount"]', "25,00")
    admin_page.check('input[name="nature"][value="geste"]', force=True)
    admin_page.fill('input[name="reason"]', "Bureau du 12/03")
    admin_page.get_by_role("button", name="Abandonner").click()
    admin_page.wait_for_load_state("domcontentloaded")
    expect(admin_page.locator(".confirm", has_text="ne doit plus rien")).to_have_count(1)

    abandon_key = admin_page.locator('form:has(input[name="del_kind"][value="abandon"]) input[name="del_key"]').get_attribute("value")
    delete_row(admin_page, module_url, seed["camille_id"], abandon_key)
    assert owed(admin_page, module_url) == "25,00 €"
