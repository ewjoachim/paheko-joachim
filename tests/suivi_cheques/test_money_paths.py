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


def _record(page: Page, module_url: str, kind: str, row_text: str):
    """Click "Comptabiliser" on the queue row of that kind (the queue has one table
    per kind, and a cancellation and its settlement both name the same cheque)."""
    page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    row = page.locator(f'tr:has(input[name="rec_kind"][value="{kind}"])').filter(
        has_text=row_text
    )
    expect(row).to_have_count(1)
    row.get_by_role("button", name="Comptabiliser").click()
    page.wait_for_load_state("domcontentloaded")


def test_a_cancellation_and_its_settlement_are_two_entries(
    admin_page: Page, module_url: str, reseed, transaction
):
    """CHQ-0141 (30,00) bounced and was settled by a new cheque, CHQ-0200. Each fact
    gets its own entry, dated when it happened:

      - the cancellation: the cheque leaves the waiting account, the member owes it
        (credit 5112 = 3000, debit 411 = 3000);
      - the settlement: the new cheque enters the waiting account and the debt is
        extinguished (debit 5112 = 3000, credit 411 = 3000).

    Both nets to zero on 5112 and on 411, which is what a single entry used to say
    in one go — for a cancellation whose replacement was typed at the same moment,
    and only then."""
    reseed()

    _record(admin_page, module_url, "annul_pay", "CHQ-0141")
    cancellation = transaction(f"Annulation chèque n°CHQ-0141 — {MEMBER}")
    assert cancellation["found"]
    debit, credit = _totals(cancellation["lines"])
    assert debit == credit == 3000, cancellation["lines"]
    assert any(
        l["account"] == "5112" and l["credit"] == 3000 and l["ref"] == "CHQ-0141"
        for l in cancellation["lines"]
    ), cancellation["lines"]
    assert any(
        l["account"] == "411" and l["debit"] == 3000 for l in cancellation["lines"]
    ), cancellation["lines"]

    _record(admin_page, module_url, "settlement", "CHQ-0141")
    settlement = transaction(f"Règlement créance — chèque annulé n°CHQ-0141 — {MEMBER}")
    assert settlement["found"]
    debit, credit = _totals(settlement["lines"])
    assert debit == credit == 3000, settlement["lines"]
    assert any(
        l["account"] == "5112" and l["debit"] == 3000 for l in settlement["lines"]
    ), "the settling cheque enters the waiting account"
    assert any(
        l["account"] == "411" and l["credit"] == 3000 for l in settlement["lines"]
    ), "and the debt is extinguished"


def test_cancel_deposit_slip_unlocks_cheques(
    admin_page: Page, module_url: str, reseed
):
    """A not-yet-recorded slip can be cancelled: it leaves the queue and its
    cheque returns to the deposit selection (batch_id cleared)."""
    reseed()
    admin_page.on("dialog", lambda d: d.accept())  # the "are you sure?" confirm
    admin_page.goto(f"{module_url}/batch.html?batch=DEMO", wait_until="domcontentloaded")

    admin_page.get_by_role("button", name="Annuler le bordereau").click()
    admin_page.wait_for_load_state("domcontentloaded")
    expect(admin_page.locator(".confirm")).to_contain_text("annulé")

    # Gone from the "to record" queue...
    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    expect(
        admin_page.locator('form:has(input[name="rec_id"][value="DEMO"])')
    ).to_have_count(0)
    # ...and CHQ-0143 is selectable again when preparing a July slip.
    admin_page.goto(f"{module_url}/index.html?period=2026-07&state=todo", wait_until="domcontentloaded")
    expect(admin_page.locator("table.list", has_text="CHQ-0143")).to_have_count(1)
