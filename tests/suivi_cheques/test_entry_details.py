"""What an entry says about the member, and how the module points back to it.

Naming the member matters twice over: in the journal a bare « Créance — chèque
annulé n°X » says nothing about who owes the money, and the link into
acc_transactions_users is what makes the member show up in the core's own
« Comptes de membres » balance page.
"""

import re

from playwright.sync_api import Page, expect

MEMBER = "Camille Martin"
ENTRY_LINK = 'a[href*="acc/transactions/details.php?id="]'


def _entry_id_from_link(page: Page) -> int:
    href = page.locator(f".confirm {ENTRY_LINK}").first.get_attribute("href")
    return int(re.search(r"id=(\d+)", href).group(1))


def test_cancellation_names_the_member(
    admin_page: Page, module_url, reseed, module_config, transaction, seed
):
    """CHQ-0140 cancelled with nothing replacing it: the member owes 45,00, and both
    the entry label and the receivable line say who."""
    reseed()
    module_config(auto_record_cancellations=1)

    admin_page.goto(f"{module_url}/edit.html?payment={seed['pay_edit']}", wait_until="domcontentloaded")
    admin_page.check('input[name="cancelled"]')
    admin_page.fill('input[name="reason"]', "Chèque perdu")
    admin_page.get_by_role("button", name="Enregistrer").click()
    admin_page.wait_for_load_state("domcontentloaded")

    txn = transaction(f"Annulation chèque n°CHQ-0140 — {MEMBER}")
    assert txn["found"], "the label no longer carries the member name"

    receivable = [l for l in txn["lines"] if l["account"] == "411"]
    assert len(receivable) == 1, txn["lines"]
    assert MEMBER in receivable[0]["label"], receivable[0]["label"]

    assert txn["users"] == [int(seed["camille_id"])], txn["users"]


def test_deposit_entry_is_linked_to_its_members(
    admin_page: Page, module_url, reseed, module_config, transaction, seed
):
    """The slip covers several cheques of the same member: the entry links them
    once, not once per cheque (the ids are deduplicated before being sent)."""
    reseed()
    module_config(auto_record_deposits=1)

    admin_page.goto(f"{module_url}/index.html?period=2026-09&state=todo", wait_until="domcontentloaded")
    boxes = admin_page.locator('input[type="checkbox"][name^="deposit["]')
    count = boxes.count()
    assert count > 1, "this test needs a slip with more than one cheque"
    for i in range(count):
        boxes.nth(i).check()
    admin_page.get_by_role("button", name="Générer le bordereau").click()
    admin_page.wait_for_load_state("domcontentloaded")

    ref = re.search(r"[?&]batch=([^&]+)", admin_page.url).group(1)
    txn = transaction(f"Remise de chèques n°{ref}")
    assert txn["found"]
    assert txn["users"] == [int(seed["camille_id"])], txn["users"]


def test_automatic_mode_links_to_the_created_entry(
    admin_page: Page, module_url, reseed, module_config, transaction, seed
):
    reseed()
    module_config(auto_record_cancellations=1)

    admin_page.goto(f"{module_url}/edit.html?payment={seed['pay_edit']}", wait_until="domcontentloaded")
    admin_page.check('input[name="cancelled"]')
    admin_page.get_by_role("button", name="Enregistrer").click()
    admin_page.wait_for_load_state("domcontentloaded")

    expect(admin_page.locator(f".confirm {ENTRY_LINK}")).to_have_count(1)
    txn = transaction(f"Annulation chèque n°CHQ-0140 — {MEMBER}")
    assert _entry_id_from_link(admin_page) == txn["id"], "the link points at another entry"


def test_the_queue_links_to_the_created_entry(
    admin_page: Page, module_url, reseed, transaction
):
    """Same link on the manual path, where the entry is posted from the queue."""
    reseed()
    admin_page.goto(f"{module_url}/to_record.html", wait_until="domcontentloaded")
    slip = admin_page.locator('form:has(input[name="rec_id"][value="DEMO"])')
    expect(slip).to_have_count(1)
    slip.get_by_role("button", name="Comptabiliser").click()
    admin_page.wait_for_load_state("domcontentloaded")

    expect(admin_page.locator(f".confirm {ENTRY_LINK}")).to_have_count(1)
    txn = transaction("Remise de chèques n°DEMO")
    assert txn["found"]
    assert _entry_id_from_link(admin_page) == txn["id"]
