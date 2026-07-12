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
def module_url() -> str:
    """Base URL of the suivi_cheques module."""
    return f"{BASE_URL}/m/suivi_cheques"


@pytest.fixture
def reseed():
    """Reset the demo fixture to a pristine state (call at the start of a test
    that mutates data, so it doesn't depend on other tests' order)."""
    seed_php = (REPO_ROOT / "doc-tools" / "seed-demo.php").read_text()

    def _do() -> None:
        _php(seed_php)

    return _do


# Fetch the latest accounting transaction with a given label, so tests can
# assert the module posted a balanced, correctly-split entry. Returns
# {found, id, lines:[{account, debit, credit, ref}]} as JSON.
_TXN_PHP = """<?php
namespace Paheko;
require '/var/www/paheko/include/init.php';
$db = DB::getInstance();
$label = base64_decode('%s');
$id = $db->firstColumn('SELECT id FROM acc_transactions WHERE label = ? ORDER BY id DESC LIMIT 1', $label);
if (!$id) { echo json_encode(['found' => false]); exit; }
$rows = $db->get('SELECT a.code AS account, l.debit AS debit, l.credit AS credit, l.reference AS ref
    FROM acc_transactions_lines l INNER JOIN acc_accounts a ON a.id = l.id_account
    WHERE l.id_transaction = ? ORDER BY l.id', $id);
echo json_encode([
    'found' => true,
    'id' => (int) $id,
    'lines' => array_map(fn($r) => [
        'account' => $r->account,
        'debit' => (int) $r->debit,
        'credit' => (int) $r->credit,
        'ref' => $r->ref,
    ], $rows),
]);
"""


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
