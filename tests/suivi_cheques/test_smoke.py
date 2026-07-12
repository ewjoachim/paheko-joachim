"""Smoke tests: every module page opens without error and lands on its tab."""

import pytest
from playwright.sync_api import Page, expect

# (path under /m/suivi_cheques/, expected highlighted tab label)
PAGES = [
    ("", "Mois courant"),
    ("upcoming.html", "Mois à venir"),
    ("exercise.html", "Année en cours"),
    ("to_record.html", "À comptabiliser"),
    ("config.html", "Configuration"),
]


@pytest.mark.parametrize("path, tab_label", PAGES, ids=[p[1] for p in PAGES])
def test_page_opens_on_its_tab(
    admin_page: Page, module_url: str, path: str, tab_label: str
):
    resp = admin_page.goto(f"{module_url}/{path}", wait_until="domcontentloaded")
    assert resp is not None and resp.ok, f"HTTP {resp.status if resp else '??'} for {path}"

    # Paheko renders uncaught exceptions in a .error/.exception block.
    assert admin_page.locator(".error, .exception").count() == 0, (
        f"error block on {path or 'index'}"
    )

    # The shared tab bar rendered and highlights exactly the current page.
    current = admin_page.locator("nav.tabs li.current")
    expect(current).to_have_count(1)
    expect(current).to_contain_text(tab_label)
