"""Shared fixtures for the suivi_cheques end-to-end tests.

The tests drive the real Paheko UI (Playwright), against a freshly installed +
seeded throwaway instance (see doc-tools/bootstrap-instance.php + seed-demo.php).
Configuration comes from the environment, matching doc-tools/screenshots.mjs:

    BASE_URL        default http://localhost:8095
    ADMIN_EMAIL     default admin@example.org
    ADMIN_PASSWORD  default demo-screenshots-2026
    CAMILLE_ID      default 2   (seeded demo member)
    PAY_EDIT        default 1   (seeded cheque payment id)
"""

import base64
import json
import os
import re
import shlex
import subprocess
from pathlib import Path

import pytest
from playwright.sync_api import Page

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8095").rstrip("/")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.org")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "demo-screenshots-2026")

REPO_ROOT = Path(__file__).resolve().parent.parent
# How to run php inside the instance container. Local dev uses podman; CI sets
# this to the docker equivalent.
CONTAINER_EXEC = os.environ.get(
    "CONTAINER_EXEC", "podman exec -i -u www-data paheko-ci"
)


def _php(code: str) -> str:
    """Run a PHP snippet inside the instance container, return its stdout."""
    proc = subprocess.run(
        [*shlex.split(CONTAINER_EXEC), "php"],
        input=code,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"container php failed (rc={proc.returncode}):\n{proc.stderr}\n{proc.stdout}"
        )
    return proc.stdout


@pytest.fixture
def add_to_slip():
    """Tick nothing, just push the ticked cheques into a new slip and open it.

    A slip is born *en cours*: it is only the trip to the bank that freezes it and
    makes it something to record, which is what take_to_bank() does next."""

    def _do(page) -> None:
        page.get_by_role("button", name="Ajouter au bordereau").click()
        page.wait_for_load_state("domcontentloaded")

    return _do


@pytest.fixture
def take_to_bank():
    """Mark the slip the page is on as physically deposited, and return its ref."""

    def _do(page) -> str:
        page.get_by_role("button", name="Marquer comme déposé").click()
        page.wait_for_load_state("domcontentloaded")
        return re.search(r"[?&]batch=([^&]+)", page.url).group(1)

    return _do


@pytest.fixture
def module_url() -> str:
    """Base URL of the suivi_cheques module."""
    return f"{BASE_URL}/m/suivi_cheques"


# seed-demo.php purges module data and the till, but not accounting: entries
# posted by an earlier test would still be found by the `transaction` fixture, so
# tests could not assert that nothing was posted. Wipe them here (throwaway db).
_PURGE_ACCOUNTING_PHP = """<?php
namespace Paheko;
require '/var/www/paheko/include/init.php';
$db = DB::getInstance();
$db->exec('DELETE FROM acc_transactions_lines;
    DELETE FROM acc_transactions_links;
    DELETE FROM acc_transactions_users;
    DELETE FROM acc_transactions_files;
    DELETE FROM acc_transactions;');
"""


@pytest.fixture
def purge_accounting():
    """Delete every accounting entry, leaving module data untouched — lets a test
    simulate the accountant deleting an entry the module still points to."""

    def _do() -> None:
        _php(_PURGE_ACCOUNTING_PHP)

    return _do


@pytest.fixture
def reseed(purge_accounting):
    """Reset the demo fixture to a pristine state (call at the start of a test
    that mutates data, so it doesn't depend on other tests' order)."""
    seed_php = (REPO_ROOT / "doc-tools" / "seed-demo.php").read_text()

    def _do() -> None:
        purge_accounting()
        _php(seed_php)

    return _do


# Fetch the latest accounting transaction with a given label, so tests can assert
# the module posted a balanced, correctly-split entry. Returns
# {found, id, lines:[{account, debit, credit, ref, label}], users:[id_user]} as JSON.
# `users` is grouped: acc_transactions_users can hold several rows per member
# (one per linked subscription), and only the distinct members matter here.
_TXN_PHP = """<?php
namespace Paheko;
require '/var/www/paheko/include/init.php';
$db = DB::getInstance();
$label = base64_decode('%s');
$id = $db->firstColumn('SELECT id FROM acc_transactions WHERE label = ? ORDER BY id DESC LIMIT 1', $label);
if (!$id) { echo json_encode(['found' => false]); exit; }
$rows = $db->get('SELECT a.code AS account, l.debit AS debit, l.credit AS credit,
    l.reference AS ref, l.label AS label
    FROM acc_transactions_lines l INNER JOIN acc_accounts a ON a.id = l.id_account
    WHERE l.id_transaction = ? ORDER BY l.id', $id);
$users = $db->get('SELECT id_user FROM acc_transactions_users
    WHERE id_transaction = ? GROUP BY id_user ORDER BY id_user', $id);
echo json_encode([
    'found' => true,
    'id' => (int) $id,
    'lines' => array_map(fn($r) => [
        'account' => $r->account,
        'debit' => (int) $r->debit,
        'credit' => (int) $r->credit,
        'ref' => $r->ref,
        'label' => $r->label,
    ], $rows),
    'users' => array_map(fn($r) => (int) $r->id_user, $users),
]);
"""


# Patch the module configuration in place, merging into the existing JSON exactly
# like {{:save key="config"}} does.
_CONFIG_PHP = """<?php
namespace Paheko;
require '/var/www/paheko/include/init.php';
$db = DB::getInstance();
$patch = json_decode(base64_decode('%s'), true);
$cur = json_decode((string) $db->firstColumn('SELECT config FROM modules WHERE name = ?', 'suivi_cheques'), true) ?: [];
$db->preparedQuery('UPDATE modules SET config = ? WHERE name = ?', json_encode(array_merge($cur, $patch)), 'suivi_cheques');
"""


@pytest.fixture
def module_config():
    """Set suivi_cheques configuration keys. Call it after reseed(), which resets
    the config to the demo defaults (no automatic recording)."""

    def _set(**values) -> None:
        b64 = base64.b64encode(json.dumps(values).encode()).decode()
        _php(_CONFIG_PHP % b64)

    return _set


# Add a till cheque with NO module overlay, so its collection month comes from the
# payment method mapping — the branch seed-demo.php never exercises, since every
# seeded cheque carries an explicit planned_month.
_PAYMENT_PHP = """<?php
namespace Paheko;
require '/var/www/paheko/include/init.php';
$db = DB::getInstance();
$p = json_decode(base64_decode('%s'), true);
$tab = $db->firstColumn('SELECT id FROM plugin_pos_tabs ORDER BY id DESC LIMIT 1');
$db->preparedQuery(
    "INSERT INTO plugin_pos_tabs_payments (tab, method, date, amount, reference, account, type) VALUES (?, ?, ?, ?, ?, '5112', 0);",
    $tab, $p['method'], $p['date'], $p['amount'], $p['reference']
);
echo (int) $db->lastInsertId();
"""


@pytest.fixture
def till_payment():
    """Insert a till cheque on the seeded tab. Call it after reseed()."""

    def _add(method: int, date: str, amount: int, reference: str) -> int:
        b64 = base64.b64encode(
            json.dumps(
                {
                    "method": method,
                    "date": date,
                    "amount": amount,
                    "reference": reference,
                }
            ).encode()
        ).decode()
        return int(_php(_PAYMENT_PHP % b64).strip())

    return _add


# A slate debt on a tab that was never linked to a member's record. Real money
# owed, but it cannot appear in a per-member list — the debtors page has to
# announce it separately rather than let its total lie.
_ORPHAN_SLATE_PHP = """<?php
namespace Paheko;
require '/var/www/paheko/include/init.php';
$db = DB::getInstance();
$sid = $db->firstColumn('SELECT id FROM plugin_pos_sessions ORDER BY id LIMIT 1');
$db->preparedQuery("INSERT INTO plugin_pos_tabs (session, name, user_id, opened, closed)
    VALUES (?, 'Passant sans fiche', NULL, '2026-07-05 10:00:00', '2026-07-05 10:05:00');", $sid);
$tab = $db->lastInsertId();
$db->preparedQuery("INSERT INTO plugin_pos_tabs_items (tab, added, qty, price, total, name, category_name, account, type)
    VALUES (?, '2026-07-05 10:01:00', 1, %d, %d, 'Vente au comptoir', 'Vente', '707', 0);", $tab);
$db->preparedQuery("INSERT INTO plugin_pos_tabs_payments (tab, method, date, amount, reference, account, type)
    VALUES (?, 3, '2026-07-05', %d, NULL, '4110', 2);", $tab);
"""


@pytest.fixture
def orphan_slate_debt():
    """Add a slate debt on a tab with no member link. Call after reseed()."""

    def _add(cents: int) -> None:
        _php(_ORPHAN_SLATE_PHP % (cents, cents, cents))

    return _add


# An entry the module did not create, moving a third-party account and linked to a
# member — a subscription typed straight into accounting, say. The debtors page
# cannot show it (it does not own it), so it has to announce the gap instead of
# implying its table is exhaustive. Same path as the API endpoint the module uses.
_MANUAL_RECEIVABLE_PHP = """<?php
namespace Paheko;
use Paheko\\Entities\\Accounting\\Transaction;
require '/var/www/paheko/include/init.php';
$p = json_decode(base64_decode('%s'), true);
$t = new Transaction;
$t->importFromAPI([
    'id_year' => 'current',
    'type' => 'advanced',
    'date' => $p['date'],
    'label' => 'Cotisation saisie a la main',
    'lines' => [
        ['account' => '411', 'debit' => $p['amount'], 'credit' => '0'],
        ['account' => '756', 'debit' => '0', 'credit' => $p['amount']],
    ],
]);
$t->save();
$t->updateLinkedUsers([(int) $p['user']]);
echo (int) $t->id();
"""


@pytest.fixture
def manual_receivable():
    """Post a third-party entry outside the module, linked to a member."""

    def _add(user: int, amount: str, date: str = "2026-07-10") -> int:
        b64 = base64.b64encode(
            json.dumps({"user": user, "amount": amount, "date": date}).encode()
        ).decode()
        return int(_php(_MANUAL_RECEIVABLE_PHP % b64).strip())

    return _add


@pytest.fixture
def transaction():
    def _get(label: str) -> dict:
        b64 = base64.b64encode(label.encode()).decode()
        return json.loads(_php(_TXN_PHP % b64))

    return _get


@pytest.fixture
def seed() -> dict:
    """Ids produced by seed-demo.php (env-overridable)."""
    return {
        "camille_id": os.environ.get("CAMILLE_ID", "2"),
        "pay_edit": os.environ.get("PAY_EDIT", "1"),
    }


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict) -> dict:
    # Deterministic rendering: retina, French locale, forced light theme —
    # same as the screenshot pipeline so captures and tests agree.
    return {
        **browser_context_args,
        "viewport": {"width": 1200, "height": 900},
        "device_scale_factor": 2,
        "locale": "fr-FR",
        "color_scheme": "light",
        "base_url": BASE_URL,
    }


@pytest.fixture(autouse=True)
def _strip_view_transition(context) -> None:
    """Paheko enables `@view-transition { navigation: auto }`, which freezes
    headless screenshots (and stalls navigations) — strip that one rule from
    every stylesheet, leaving the rest of the CSS intact."""
    import re

    def handler(route):
        resp = route.fetch()
        css = re.sub(r"@view-transition\s*\{[^}]*\}", "", resp.text(), flags=re.I)
        route.fulfill(response=resp, body=css)

    context.route(re.compile(r"\.css(\?|$)"), handler)


@pytest.fixture
def admin_page(page: Page) -> Page:
    """A page logged in as the instance administrator."""
    page.set_default_timeout(15000)
    page.goto(f"{BASE_URL}/admin/login.php", wait_until="domcontentloaded")
    page.fill('input[name="id"]', ADMIN_EMAIL)
    page.fill('input[name="password"]', ADMIN_PASSWORD)
    page.click('button[type="submit"], input[type="submit"]')
    page.wait_for_load_state("domcontentloaded")
    assert page.locator('input[name="password"]').count() == 0, (
        "login failed — check ADMIN_EMAIL / ADMIN_PASSWORD and that the "
        "instance was seeded"
    )
    return page
