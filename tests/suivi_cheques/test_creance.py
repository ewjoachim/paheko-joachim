"""Life of a receivable: born with a cancellation, collected at the desk.

The receivable is a document of this module, not a reading of the accounts. Every
test here therefore checks behaviour with accounting empty or irrelevant — the
point being that a debt is visible and settleable before, and independently of,
anyone posting an entry.
"""

from urllib.parse import urljoin

from playwright.sync_api import Page, expect


def owed(page: Page, module_url, name: str = "Camille Martin") -> str:
    """The receivable cell for a member on the debtors page ("—" when nothing)."""
    page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")
    row = page.locator("table.list tbody tr", has_text=name)
    if row.count() == 0:
        return "—"
    return row.locator("td").nth(2).inner_text().strip()


def cancel(page: Page, module_url, pid: str, reason: str = "Chèque sans provision"):
    page.goto(f"{module_url}/edit.html?payment={pid}", wait_until="domcontentloaded")
    page.check('input[name="cancelled"]')
    page.fill('input[name="reason"]', reason)
    page.get_by_role("button", name="Enregistrer").click()
    page.wait_for_load_state("domcontentloaded")


def settle(page: Page, module_url, user: str, amount: str | None = None):
    page.goto(f"{module_url}/settle.html?user={user}", wait_until="domcontentloaded")
    if amount is not None:
        page.fill('input[name="amount"]', amount)
    page.locator('select[name="method"]').select_option(label="Espèces")
    page.get_by_role("button", name="Enregistrer le règlement").click()
    page.wait_for_load_state("domcontentloaded")


def test_cancelling_creates_the_debt_with_no_entry(
    admin_page: Page, module_url, reseed, seed, transaction
):
    """Cancelling CHQ-0140 (45,00) with no replacement leaves the whole amount
    owed, and does so without any accounting: automatic recording is off, so the
    entry is still sitting in the queue."""
    reseed()
    cancel(admin_page, module_url, seed["pay_edit"])

    assert not transaction("Annulation chèque n°CHQ-0140 — Camille Martin")["found"]
    # 25,00 seeded on CHQ-0142 + 45,00 from CHQ-0140.
    assert owed(admin_page, module_url) == "70,00 €"


def test_a_replacement_shrinks_the_debt_to_nothing(
    admin_page: Page, module_url, reseed, seed
):
    """The debt is the uncovered remainder, so it follows the replacements — the
    same computation the cancellation entry uses (_cancellation_shape.html), which
    is why they cannot disagree."""
    reseed()
    admin_page.goto(
        f"{module_url}/edit.html?payment={seed['pay_edit']}", wait_until="domcontentloaded"
    )
    admin_page.check('input[name="cancelled"]')
    admin_page.locator('input[name="rc_number[]"]').first.fill("CHQ-0301")
    admin_page.locator('input[name="rc_amount[]"]').first.fill("45,00")
    admin_page.locator('select[name="rc_month[]"]').first.select_option("9")
    admin_page.get_by_role("button", name="Enregistrer").click()
    admin_page.wait_for_load_state("domcontentloaded")

    # Fully replaced: only the seeded 25,00 remains.
    assert owed(admin_page, module_url) == "25,00 €"


def test_a_cancelled_replacement_still_covers_its_parent(
    admin_page: Page, module_url, reseed
):
    """CHQ-0141 (30,00) was cancelled and fully replaced by CHQ-0200, which then
    bounces too. CHQ-0200 owes 30,00 — and CHQ-0141 must NOT also owe 30,00: the
    money went missing once, not twice.

    The cheque was really handed over, so it still covers its parent; its own
    bouncing is its own cancellation's business. That is what "one level at a
    time" means, and re-saving the parent must not change the total."""
    reseed()

    admin_page.goto(
        f"{module_url}/edit_replacement.html?key=rempl-demo-0200",
        wait_until="domcontentloaded",
    )
    admin_page.check('input[name="cancelled"]')
    admin_page.fill('input[name="reason"]', "Chèque de remplacement sans provision")
    admin_page.get_by_role("button", name="Enregistrer").click()
    admin_page.wait_for_load_state("domcontentloaded")

    # 25,00 seeded on CHQ-0142 + 30,00 on CHQ-0200.
    assert owed(admin_page, module_url) == "55,00 €"

    # Re-saving the parent's sheet changes nothing: it is not a new debt.
    admin_page.goto(f"{module_url}/edit.html?payment=2", wait_until="domcontentloaded")
    admin_page.get_by_role("button", name="Enregistrer").click()
    admin_page.wait_for_load_state("domcontentloaded")

    assert owed(admin_page, module_url) == "55,00 €"


def test_uncancelling_removes_the_debt(admin_page: Page, module_url, reseed, seed):
    reseed()
    cancel(admin_page, module_url, seed["pay_edit"])
    assert owed(admin_page, module_url) == "70,00 €"

    admin_page.goto(
        f"{module_url}/edit.html?payment={seed['pay_edit']}", wait_until="domcontentloaded"
    )
    admin_page.uncheck('input[name="cancelled"]')
    admin_page.get_by_role("button", name="Enregistrer").click()
    admin_page.wait_for_load_state("domcontentloaded")

    assert owed(admin_page, module_url) == "25,00 €"


def test_partial_settlement_leaves_the_remainder(admin_page: Page, module_url, reseed, seed):
    """Paying 10,00 of the seeded 25,00 leaves 15,00 owed, and the settle page
    still offers the rest — defaulting to what is left, not to the original."""
    reseed()
    settle(admin_page, module_url, seed["camille_id"], "10,00")
    assert owed(admin_page, module_url) == "15,00 €"

    admin_page.goto(
        f"{module_url}/settle.html?user={seed['camille_id']}", wait_until="domcontentloaded"
    )
    expect(admin_page.locator("h2", has_text="CHQ-0142")).to_contain_text("reste 15,00")
    assert admin_page.locator('input[name="amount"]').input_value() == "15,00"


def test_overpaying_is_refused(admin_page: Page, module_url, reseed, seed):
    """An excess payment is not a settlement, it is an advance — a different thing
    this module does not track, so it is rejected rather than silently absorbed."""
    reseed()
    settle(admin_page, module_url, seed["camille_id"], "30,00")

    expect(admin_page.locator(".error, .block.error")).to_contain_text("25,00")
    assert owed(admin_page, module_url) == "25,00 €", "nothing may have been recorded"


def test_uncancelling_after_a_settlement_is_refused(
    admin_page: Page, module_url, reseed, seed
):
    """Un-cancelling would delete a debt that has been partly paid — erasing a
    recorded collection. The form must refuse and keep everything."""
    reseed()
    settle(admin_page, module_url, seed["camille_id"], "10,00")

    # Reach the sheet of the cheque that produced the debt (CHQ-0142) the way an
    # operator would: through the month listing.
    admin_page.goto(f"{module_url}/index.html?month=2026-07", wait_until="domcontentloaded")
    edit = (
        admin_page.locator("tr", has_text="CHQ-0142")
        .get_by_role("link", name="Modifier / annuler")
        .first
    )
    # The module links its own pages relatively, and page.goto() resolves a
    # relative URL against base_url, not against the current page.
    admin_page.goto(
        urljoin(admin_page.url, edit.get_attribute("href")), wait_until="domcontentloaded"
    )
    admin_page.uncheck('input[name="cancelled"]')
    admin_page.get_by_role("button", name="Enregistrer").click()
    admin_page.wait_for_load_state("domcontentloaded")

    expect(admin_page.locator(".error, .block.error")).to_contain_text("déjà été réglée")
    assert owed(admin_page, module_url) == "15,00 €", "the debt must survive intact"


def test_settlement_entry_is_balanced_and_links_the_member(
    admin_page: Page, module_url, reseed, seed, transaction
):
    """What accounting gets: the collected account debited, the receivable account
    credited, and the member linked — the link the native entry form leaves
    optional, and whose omission would strand the member as a debtor forever."""
    reseed()
    settle(admin_page, module_url, seed["camille_id"])

    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    admin_page.locator("tr", has_text="CHQ-0142").get_by_role(
        "button", name="Comptabiliser"
    ).last.click()
    admin_page.wait_for_load_state("domcontentloaded")

    txn = transaction("Règlement créance — chèque annulé n°CHQ-0142 — Camille Martin")
    assert txn["found"], "the settlement entry was not posted"
    assert txn["users"] == [int(seed["camille_id"])], "the member must be linked"

    accounts = {(l["account"], l["debit"], l["credit"]) for l in txn["lines"]}
    assert ("411", 0, 2500) in accounts, f"receivable not credited: {txn['lines']}"
    assert sum(l["debit"] for l in txn["lines"]) == sum(
        l["credit"] for l in txn["lines"]
    ), "entry must balance"


def test_accounting_moved_outside_the_module_is_announced(
    admin_page: Page, module_url, reseed, seed, manual_receivable
):
    """The module owns its receivables, but nothing stops accounting from moving a
    third-party account on its own. The page says so rather than implying its table
    is the whole truth."""
    reseed()
    admin_page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")
    expect(
        admin_page.locator(".block.alert", has_text="comptes de tiers")
    ).to_have_count(0)

    manual_receivable(user=int(seed["camille_id"]), amount="12,00")
    admin_page.goto(f"{module_url}/debtors.html", wait_until="domcontentloaded")

    warning = admin_page.locator(".block.alert", has_text="comptes de tiers")
    expect(warning).to_contain_text("12,00 €")
    # And it is not folded into the per-member figures, which stay the module's.
    assert owed(admin_page, module_url) == "25,00 €"
