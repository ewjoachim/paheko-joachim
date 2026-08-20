"""Capture the suivi_cheques user-guide screenshots (Python Playwright).

Run against a seeded throwaway instance (see bootstrap-instance.php +
seed-demo.php). The PNGs are NOT committed — they are regenerated in CI when the
guide is deployed, and locally via doc-tools/regen-screenshots.sh.

    uv run --with playwright playwright install chromium
    uv run --with playwright python doc-tools/screenshots.py

Environment (matches seed-demo.php's output):
    BASE_URL        default http://localhost:8095
    ADMIN_EMAIL, ADMIN_PASSWORD, CAMILLE_ID, PAY_EDIT
"""

import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE_URL", "http://localhost:8095").rstrip("/")
EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.org")
PASSWORD = os.environ.get("ADMIN_PASSWORD", "demo-screenshots-2026")
# Same defaults as tests/conftest.py: what seed-demo.php produces on a fresh
# instance. Without them the ids were empty, and two shots silently captured an
# error page and an empty form — neither workflow passes these variables.
CAMILLE = os.environ.get("CAMILLE_ID", "2")
PAY_EDIT = os.environ.get("PAY_EDIT", "1")

OUT = Path(__file__).resolve().parent.parent / "doc" / "suivi_cheques" / "screenshots"
M = f"{BASE}/m/suivi_cheques"

# (filename, url, wait-for selector)
SHOTS = [
    ("01-cheques-du-mois.png", f"{M}/", "table.list"),
    ("02-a-venir.png", f"{M}/upcoming.html", "table.list"),
    ("03-annuler.png", f"{M}/edit.html?payment={PAY_EDIT}", "form"),
    ("04-preparer-bordereau.png", f"{M}/deposit.html?month=2026-07", "table.list"),
    ("05-bordereau.png", f"{M}/deposit.html?batch=DEMO", "table.list"),
    ("06-bordereaux.png", f"{M}/batches.html", "table.list"),
    # The seeded cancellation leaves Camille a receivable on top of her slate, so
    # this shows a member owing on both sides with nothing posted to accounting —
    # which is the point the page makes. It used to need a "Comptabiliser" click
    # first, back when a receivable only existed as an accounting line.
    ("07-impayes.png", f"{M}/debtors.html", "table.list"),
    ("08-regler-creance.png", f"{M}/settle.html?user={CAMILLE}", "form"),
    ("09-a-comptabiliser.png", f"{M}/to_record.html", "table.list"),
    ("10-fiche-membre.png", f"{BASE}/admin/users/details.php?id={CAMILLE}", "table.list"),
    ("11-configuration.png", f"{M}/config.html", "form"),
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1200, "height": 900},
            device_scale_factor=2,  # sharp (retina) captures
            color_scheme="light",
            locale="fr-FR",
        )

        # Paheko enables View Transitions (`@view-transition { navigation: auto }`),
        # which freezes headless screenshots (the compositor stays blocked after
        # navigation). Strip that rule on the fly — the rest of the CSS is intact.
        def strip_view_transition(route):
            resp = route.fetch()
            css = re.sub(r"@view-transition\s*\{[^}]*\}", "", resp.text(), flags=re.I)
            route.fulfill(response=resp, body=css)

        context.route(re.compile(r"\.css(\?|$)"), strip_view_transition)

        page = context.new_page()
        page.set_default_timeout(15000)

        page.goto(f"{BASE}/admin/login.php", wait_until="domcontentloaded")
        page.fill('input[name="id"]', EMAIL)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"], input[type="submit"]')
        page.wait_for_load_state("domcontentloaded")
        if page.locator('input[name="password"]').count():
            print("Login FAILED — check ADMIN_EMAIL / ADMIN_PASSWORD.", file=sys.stderr)
            browser.close()
            return 1
        print("Logged in.")

        failed = []

        for name, url, wait_for in SHOTS:
            try:
                page.goto(url, wait_until="domcontentloaded")
                # A missing selector means the page did not render what we came for
                # (renamed page, error page, permission denied). Letting it through
                # would publish that error straight into the user guide, so it has
                # to fail — loudly, and with a non-zero exit for CI.
                if wait_for:
                    page.wait_for_selector(wait_for, timeout=5000)
                page.screenshot(path=str(OUT / name), full_page=True)
                print(f"✓ {name}")
            except Exception as e:  # noqa: BLE001 — report every shot, fail at the end
                print(f"✗ {name} : {e}", file=sys.stderr)
                failed.append(name)

        browser.close()

    if failed:
        print(f"\n{len(failed)} capture(s) en échec : {', '.join(failed)}", file=sys.stderr)
        return 1

    print(f"\nScreenshots written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
