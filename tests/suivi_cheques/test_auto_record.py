"""Automatic recording: when the matching configuration checkbox is ticked, the
module posts the accounting entry straight away instead of parking the item in the
"to record" queue — mirroring the till's "create the accounting entries
automatically" setting.

The default (no checkbox) is asserted too, since that is the behaviour the whole
"comptabilité validates everything" workflow relies on.
"""

import re

from playwright.sync_api import Page, expect

MEMBER = "Camille Martin"  # seeded demo member; the entry label now names them


def _totals(lines: list[dict]) -> tuple[int, int]:
    return sum(l["debit"] for l in lines), sum(l["credit"] for l in lines)


def _cancel_cheque(page: Page, module_url: str, pid: str) -> None:
    """Tick "cheque not cashed" on a till cheque and save."""
    page.goto(f"{module_url}/edit.html?payment={pid}", wait_until="domcontentloaded")
    page.check('input[name="cancelled"]')
    page.fill('input[name="reason"]', "Chèque perdu")
    page.get_by_role("button", name="Enregistrer").click()
    page.wait_for_load_state("domcontentloaded")


def test_cancellation_is_recorded_immediately(
    admin_page: Page, add_to_slip, take_to_bank, module_url: str, reseed, module_config, transaction, seed
):
    """CHQ-0140 (45,00) cancelled with nothing replacing it: the entry is posted on
    save — credit waiting 5112 = 4500, debit receivable 411 = 4500 — and the cheque
    never shows up in the queue."""
    reseed()
    module_config(auto_record_cancellations=1)
    _cancel_cheque(admin_page, module_url, seed["pay_edit"])

    expect(admin_page.locator(".confirm")).to_contain_text("l'écriture comptable a été créée")

    txn = transaction(f"Annulation chèque n°CHQ-0140 — {MEMBER}")
    assert txn["found"], "the entry was not posted on save"
    debit, credit = _totals(txn["lines"])
    assert debit == credit == 4500, txn["lines"]
    assert sum(l["credit"] for l in txn["lines"] if l["account"] == "5112") == 4500
    assert any(l["account"] == "411" and l["debit"] == 4500 for l in txn["lines"])

    # Nothing left to do for the accounting side.
    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    expect(admin_page.locator("tr", has_text="CHQ-0140")).to_have_count(0)


def test_cancellation_waits_in_the_queue_by_default(
    admin_page: Page, add_to_slip, take_to_bank, module_url: str, reseed, transaction, seed
):
    """Without the checkbox, saving a cancellation posts nothing: the cheque lands
    in the queue for the accounting side to validate."""
    reseed()
    _cancel_cheque(admin_page, module_url, seed["pay_edit"])

    assert not transaction(f"Annulation chèque n°CHQ-0140 — {MEMBER}")["found"]

    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    row = admin_page.locator("tr", has_text="CHQ-0140")
    expect(row).to_have_count(1)
    expect(row.get_by_role("button", name="Comptabiliser")).to_have_count(1)


def test_deposit_slip_is_recorded_immediately(
    admin_page: Page, add_to_slip, take_to_bank, module_url: str, reseed, module_config, transaction
):
    """Taking a July slip to the bank (CHQ-0140 only, 45,00) posts the deposit entry
    on the spot: debit bank 512 = credit waiting 5112 = 4500."""
    reseed()
    module_config(auto_record_deposits=1)

    admin_page.goto(f"{module_url}/index.html?period=2026-07&state=todo", wait_until="domcontentloaded")
    # Cheques are unticked by default: take the whole slip in one click.
    admin_page.get_by_role("button", name="Tout cocher").click()
    add_to_slip(admin_page)
    take_to_bank(admin_page)

    expect(admin_page.locator(".confirm")).to_contain_text("l'écriture comptable du dépôt a été créée")
    # The slip is already marked as recorded, with a link to its entry.
    expect(admin_page.get_by_text("Dépôt comptabilisé")).to_have_count(1)

    # The batch reference is generated (timestamp), read it back from the URL.
    ref = re.search(r"[?&]batch=([^&]+)", admin_page.url).group(1)
    txn = transaction(f"Remise de chèques n°{ref}")
    assert txn["found"], "the deposit entry was not posted when the slip went to the bank"
    debit, credit = _totals(txn["lines"])
    assert debit == credit == 4500, txn["lines"]
    assert any(l["account"] == "512" and l["debit"] == 4500 for l in txn["lines"])
    assert any(
        l["account"] == "5112" and l["credit"] == 4500 and l["ref"] == "CHQ-0140"
        for l in txn["lines"]
    )

    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    expect(admin_page.locator(f'form:has(input[name="rec_id"][value="{ref}"])')).to_have_count(0)


def test_deposit_slip_waits_in_the_queue_by_default(
    admin_page: Page, add_to_slip, take_to_bank, module_url: str, reseed, transaction
):
    reseed()
    admin_page.goto(f"{module_url}/index.html?period=2026-07&state=todo", wait_until="domcontentloaded")
    # Cheques are unticked by default: take the whole slip in one click.
    admin_page.get_by_role("button", name="Tout cocher").click()
    add_to_slip(admin_page)
    take_to_bank(admin_page)

    ref = re.search(r"[?&]batch=([^&]+)", admin_page.url).group(1)
    assert not transaction(f"Remise de chèques n°{ref}")["found"]
    expect(admin_page.get_by_text("pas encore comptabilisé")).to_have_count(1)

    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    expect(admin_page.locator(f'form:has(input[name="rec_id"][value="{ref}"])')).to_have_count(1)


def test_checkboxes_round_trip_through_the_configuration_page(
    admin_page: Page, add_to_slip, take_to_bank, module_url: str, reseed
):
    """Ticking the boxes in the configuration form is enough to switch the module
    to automatic mode (the other tests set the config directly, bypassing the UI)."""
    reseed()
    admin_page.goto(f"{module_url}/config.html", wait_until="domcontentloaded")
    admin_page.check('input[name="auto_record_cancellations"]')
    admin_page.check('input[name="auto_record_deposits"]')
    admin_page.get_by_role("button", name="Enregistrer").click()
    admin_page.wait_for_load_state("domcontentloaded")

    expect(admin_page.locator(".confirm")).to_contain_text("Configuration enregistrée")
    admin_page.goto(f"{module_url}/config.html", wait_until="domcontentloaded")
    assert admin_page.is_checked('input[name="auto_record_cancellations"]')
    assert admin_page.is_checked('input[name="auto_record_deposits"]')

    # And the edit page now announces the immediate entry.
    admin_page.goto(f"{module_url}/edit.html?payment=1", wait_until="domcontentloaded")
    expect(admin_page.get_by_text("est passée immédiatement")).to_have_count(1)


def test_failed_automatic_entry_keeps_the_operational_save(
    admin_page: Page, add_to_slip, take_to_bank, module_url: str, reseed, module_config, transaction, seed
):
    """The accounting write must never take the operational save down with it: with
    a receivable account that does not exist, the entry is refused, yet the
    cancellation is stored and the cheque falls back into the queue."""
    reseed()
    module_config(auto_record_cancellations=1, receivable_account="999999")
    _cancel_cheque(admin_page, module_url, seed["pay_edit"])

    expect(admin_page.locator(".alert")).to_contain_text("n'a pas pu être créée")
    assert not transaction(f"Annulation chèque n°CHQ-0140 — {MEMBER}")["found"]

    # The cancellation itself was saved (the cheque is cancelled) and is queued.
    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    row = admin_page.locator("tr", has_text="CHQ-0140")
    expect(row).to_have_count(1)
    expect(row).to_contain_text("Chèque perdu")


def test_failed_automatic_entry_keeps_the_frozen_slip(
    admin_page: Page, add_to_slip, take_to_bank, module_url: str, reseed, module_config, transaction
):
    """Same guarantee on the deposit side: a refused entry leaves the slip frozen
    and queued, rather than losing the trip to the bank."""
    reseed()
    module_config(auto_record_deposits=1, bank_account="999999")

    admin_page.goto(f"{module_url}/index.html?period=2026-07&state=todo", wait_until="domcontentloaded")
    # Cheques are unticked by default: take the whole slip in one click.
    admin_page.get_by_role("button", name="Tout cocher").click()
    add_to_slip(admin_page)
    take_to_bank(admin_page)

    expect(admin_page.locator(".alert")).to_contain_text("n'a pas pu être créée")
    ref = re.search(r"[?&]batch=([^&]+)", admin_page.url).group(1)
    assert not transaction(f"Remise de chèques n°{ref}")["found"]
    # The slip itself exists and lists its cheque.
    expect(admin_page.locator("table.list", has_text="CHQ-0140")).to_have_count(1)

    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    expect(admin_page.locator(f'form:has(input[name="rec_id"][value="{ref}"])')).to_have_count(1)
