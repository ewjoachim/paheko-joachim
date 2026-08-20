"""Money paths: recording deposits / cancellations posts balanced accounting
entries, and a not-yet-recorded deposit slip can be cancelled.

Each mutating test calls reseed() first so it starts from a known state,
independent of the others' order. The `transaction` fixture reads the resulting
accounting entry back from the DB to assert it is balanced and split correctly.
Amounts are in cents (Paheko stores integers): 5000 = 50,00 €.
"""

from playwright.sync_api import Page, expect

MEMBER = "Camille Martin"  # seeded demo member; the entry label now names them


def _totals(lines: list[dict]) -> tuple[int, int]:
    return sum(l["debit"] for l in lines), sum(l["credit"] for l in lines)


def test_record_deposit(admin_page: Page, module_url: str, reseed, transaction):
    """Recording the demo deposit slip (1 cheque, 50,00) posts:
    debit bank 512 = credit waiting 5112 = 5000."""
    reseed()
    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")

    slip = admin_page.locator('form:has(input[name="rec_id"][value="DEMO"])')
    expect(slip).to_have_count(1)
    slip.get_by_role("button", name="Comptabiliser").click()
    admin_page.wait_for_load_state("domcontentloaded")

    expect(admin_page.locator(".confirm")).to_contain_text("Écriture comptable créée")
    # The slip is gone from the queue (now recorded).
    expect(
        admin_page.locator('form:has(input[name="rec_id"][value="DEMO"])')
    ).to_have_count(0)

    txn = transaction("Remise de chèques n°DEMO")
    assert txn["found"], "no accounting entry was created"
    debit, credit = _totals(txn["lines"])
    assert debit == credit == 5000, txn["lines"]
    assert any(l["account"] == "512" and l["debit"] == 5000 for l in txn["lines"])
    assert sum(l["credit"] for l in txn["lines"] if l["account"] == "5112") == 5000


def test_record_cancellation_with_card_and_receivable(
    admin_page: Page, module_url: str, reseed, transaction
):
    """CHQ-0142 (45,00) cancelled, 20,00 replaced by card, 25,00 left owed:
    credit waiting 5112 = 4500; debit card 512 = 2000; debit receivable 411 = 2500."""
    reseed()
    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")

    row = admin_page.locator("tr", has_text="CHQ-0142")
    expect(row).to_have_count(1)
    row.get_by_role("button", name="Comptabiliser").click()
    admin_page.wait_for_load_state("domcontentloaded")

    expect(admin_page.locator(".confirm")).to_contain_text("Écriture comptable créée")

    txn = transaction(f"Annulation chèque n°CHQ-0142 — {MEMBER}")
    assert txn["found"]
    debit, credit = _totals(txn["lines"])
    assert debit == credit == 4500, txn["lines"]
    assert sum(l["credit"] for l in txn["lines"] if l["account"] == "5112") == 4500
    assert any(l["account"] == "512" and l["debit"] == 2000 for l in txn["lines"])
    assert any(l["account"] == "411" and l["debit"] == 2500 for l in txn["lines"])


def test_record_cancellation_replaced_by_cheque(
    admin_page: Page, module_url: str, reseed, transaction
):
    """CHQ-0141 (30,00) cancelled, fully replaced by another cheque (CHQ-0200):
    the amount leaves the waiting account and the replacement re-enters it, so
    5112 is both credited and debited 3000 (net zero), no receivable."""
    reseed()
    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")

    row = admin_page.locator("tr", has_text="CHQ-0141")
    expect(row).to_have_count(1)
    row.get_by_role("button", name="Comptabiliser").click()
    admin_page.wait_for_load_state("domcontentloaded")

    txn = transaction(f"Annulation chèque n°CHQ-0141 — {MEMBER}")
    assert txn["found"]
    debit, credit = _totals(txn["lines"])
    assert debit == credit == 3000, txn["lines"]
    waiting = [l for l in txn["lines"] if l["account"] == "5112"]
    assert sum(l["credit"] for l in waiting) == 3000
    assert sum(l["debit"] for l in waiting) == 3000
    # The replacement debit line carries the new cheque number.
    assert any(l["debit"] == 3000 and l["ref"] == "CHQ-0200" for l in waiting)
    assert not any(l["account"] == "411" for l in txn["lines"])


def test_a_cancelled_replacement_still_covers_its_parent(
    admin_page: Page, module_url: str, reseed, transaction
):
    """CHQ-0200 replaced CHQ-0141 and then bounced too. CHQ-0141's entry must still
    debit the waiting account for CHQ-0200, exactly as if it had not bounced.

    The cheque was really handed over: it covers its parent, and its own bouncing
    is its own entry's business (which credits the waiting account back and posts
    the receivable). Dropping it here would credit 5112 for CHQ-0141 with no
    matching debit while CHQ-0200's entry credits a debit that never existed — and
    the same money would be owed twice, once per cheque. This is what recording
    "one level at a time" requires."""
    reseed()

    admin_page.goto(
        f"{module_url}/edit_replacement.html?key=rempl-demo-0200",
        wait_until="domcontentloaded",
    )
    admin_page.check('input[name="cancelled"]')
    admin_page.get_by_role("button", name="Enregistrer").click()
    admin_page.wait_for_load_state("domcontentloaded")

    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    admin_page.locator("tr", has_text="CHQ-0141").get_by_role(
        "button", name="Comptabiliser"
    ).click()
    admin_page.wait_for_load_state("domcontentloaded")

    txn = transaction(f"Annulation chèque n°CHQ-0141 — {MEMBER}")
    assert txn["found"]
    waiting = [l for l in txn["lines"] if l["account"] == "5112"]
    assert any(l["debit"] == 3000 and l["ref"] == "CHQ-0200" for l in waiting), (
        f"the cancelled replacement must still cover its parent: {txn['lines']}"
    )
    assert not any(l["account"] == "411" for l in txn["lines"]), (
        "nothing is left uncovered on CHQ-0141 — the debt belongs to CHQ-0200"
    )


def test_cancel_deposit_slip_unlocks_cheques(
    admin_page: Page, module_url: str, reseed
):
    """A not-yet-recorded slip can be cancelled: it leaves the queue and its
    cheque returns to the deposit selection (batch_id cleared)."""
    reseed()
    admin_page.on("dialog", lambda d: d.accept())  # the "are you sure?" confirm
    admin_page.goto(f"{module_url}/deposit.html?batch=DEMO", wait_until="domcontentloaded")

    admin_page.get_by_role("button", name="Annuler le bordereau").click()
    admin_page.wait_for_load_state("domcontentloaded")
    expect(admin_page.locator(".confirm")).to_contain_text("annulé")

    # Gone from the "to record" queue...
    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    expect(
        admin_page.locator('form:has(input[name="rec_id"][value="DEMO"])')
    ).to_have_count(0)
    # ...and CHQ-0143 is selectable again when preparing a July slip.
    admin_page.goto(f"{module_url}/deposit.html?month=2026-07", wait_until="domcontentloaded")
    expect(admin_page.locator("table.list", has_text="CHQ-0143")).to_have_count(1)
