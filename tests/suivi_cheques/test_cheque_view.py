"""The single cheque view: period bar, state chips, and the spreadsheet export."""

import zipfile

from playwright.sync_api import Page, expect

PERIODS = "nav.tabs.periods"


def test_the_period_bar_shows_the_whole_exercise(admin_page: Page, module_url, reseed):
    """Twelve months at once, plus the two overviews — no stepping month by month."""
    reseed()
    admin_page.goto(f"{module_url}/index.html", wait_until="domcontentloaded")

    items = admin_page.locator(f"{PERIODS} li")
    expect(items).to_have_count(14)
    expect(admin_page.locator(f"{PERIODS} li", has_text="À venir")).to_have_count(1)
    expect(admin_page.locator(f"{PERIODS} li", has_text="Tous")).to_have_count(1)
    # The view opens on the current month.
    expect(admin_page.locator(f"{PERIODS} li.current")).to_have_count(1)


def test_a_past_month_with_a_backlog_is_flagged(admin_page: Page, module_url, reseed):
    """CHQ-0140 is still to be collected for July 2026: the month carries the count,
    and clicking it lands on exactly those cheques. Nobody reopens a past month on
    their own, so the view has to say it."""
    reseed()
    admin_page.goto(f"{module_url}/index.html?period=all&state=all", wait_until="domcontentloaded")

    late = admin_page.locator(f'{PERIODS} a[href*="period=2026-07"]', has_text="⚠")
    expect(late).to_have_count(1)
    late.click()
    admin_page.wait_for_load_state("domcontentloaded")

    assert "period=2026-07" in admin_page.url and "state=todo" in admin_page.url
    expect(admin_page.locator("table.list tbody tr")).to_have_count(1)
    expect(admin_page.locator("table.list")).to_contain_text("CHQ-0140")


def test_the_state_chips_count_and_filter(admin_page: Page, module_url, reseed):
    """The counts answer "how many are left" without a pivot table, and an empty
    list explains itself."""
    reseed()
    admin_page.goto(f"{module_url}/index.html?period=all&state=all", wait_until="domcontentloaded")

    chips = admin_page.locator("p.actions a", has_text="encaisser")
    expect(chips).to_contain_text("À encaisser (7)")
    expect(admin_page.locator("p.actions a", has_text="Déposé")).to_contain_text("Déposé (1)")
    expect(admin_page.locator("p.actions a", has_text="Annulé")).to_contain_text("Annulé (2)")
    expect(admin_page.locator("p.actions a", has_text="Tous (")).to_contain_text("Tous (10)")

    chips.click()
    admin_page.wait_for_load_state("domcontentloaded")
    expect(admin_page.locator("table.list tbody tr")).to_have_count(7)


def test_the_period_keeps_the_state_and_the_state_keeps_the_period(
    admin_page: Page, module_url, reseed
):
    """Both live in the URL, so they survive changing month and a reload."""
    reseed()
    admin_page.goto(f"{module_url}/index.html?period=2026-07&state=cancelled", wait_until="domcontentloaded")

    month = admin_page.locator(f'{PERIODS} a[href*="period=2026-09"]').first
    assert "state=cancelled" in month.get_attribute("href")

    chip = admin_page.locator("p.actions a", has_text="Déposé")
    assert "period=2026-07" in chip.get_attribute("href")


def test_export_downloads_a_spreadsheet(admin_page: Page, module_url, reseed):
    """Every cheque, every column, no filter: it exists to be opened in a
    spreadsheet, where filtering is trivial."""
    reseed()
    admin_page.goto(f"{module_url}/index.html", wait_until="domcontentloaded")

    with admin_page.expect_download() as caught:
        admin_page.get_by_role("link", name="Exporter").click()
    path = caught.value.path()

    with zipfile.ZipFile(path) as z:
        assert z.read("mimetype").startswith(b"application/vnd.oasis.opendocument.spreadsheet")
        content = z.read("content.xml").decode()

    for column in ("Mois prévu", "N° de chèque", "Membre", "Motif d’annulation", "Notes"):
        assert column in content, f"missing column {column!r}"
    # Cancelled and deposited cheques are in there too, not just what is pending.
    for number in ("CHQ-0140", "CHQ-0141", "CHQ-0143"):
        assert number in content, f"missing cheque {number!r}"
    assert "Camille Martin" in content, "the member name is a config, not a column"
