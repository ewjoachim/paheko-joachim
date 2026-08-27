"""The single cheque view: period bar, state chips, and the spreadsheet export."""

import zipfile

import pytest
from playwright.sync_api import Page, expect

PERIODS = "nav.tabs.periods"


def test_the_period_bar_shows_the_whole_exercise(admin_page: Page, module_url, reseed):
    """Twelve months at once, plus a year either side and the two overviews — no
    stepping month by month."""
    reseed()
    admin_page.goto(f"{module_url}/index.html", wait_until="domcontentloaded")

    items = admin_page.locator(f"{PERIODS} li")
    expect(items).to_have_count(16)
    expect(admin_page.locator(f"{PERIODS} li", has_text="À venir")).to_have_count(1)
    expect(admin_page.locator(f"{PERIODS} li", has_text="Tous")).to_have_count(1)
    # The view opens on the current month.
    expect(admin_page.locator(f"{PERIODS} li.current")).to_have_count(1)


def test_the_bar_moves_a_year_at_a_time(admin_page: Page, module_url, reseed):
    """A cheque planned outside the twelve months on show has to be reachable. The
    arrows shift the whole bar by a year, and the month picked comes back with its
    own window — so stepping forward then back lands where it started."""
    reseed()
    admin_page.goto(f"{module_url}/index.html?period=2026-09&state=todo", wait_until="domcontentloaded")

    forward = admin_page.locator(f"{PERIODS} li a", has_text="2027").first
    forward.click()
    admin_page.wait_for_load_state("domcontentloaded")

    expect(admin_page.locator(f'{PERIODS} a[href*="period=2027-06"]')).to_have_count(1)
    expect(admin_page.locator(f'{PERIODS} a[href*="period=2026-09"]')).to_have_count(0)
    # The state travels along, like everywhere else in the bar.
    assert "state=todo" in admin_page.url

    back = admin_page.locator(f"{PERIODS} li a", has_text="2026").first
    back.click()
    admin_page.wait_for_load_state("domcontentloaded")
    expect(admin_page.locator(f'{PERIODS} a[href*="period=2026-09"]')).to_have_count(1)


def test_a_month_outside_the_window_is_reachable(
    admin_page: Page, module_url, reseed, till_payment
):
    """The point of the arrows: next year's cheques are listed, not lost."""
    reseed()
    # Seeded method 2 is mapped to January, so a cheque received in October 2027 is
    # planned for January 2028 — two windows past the open exercise.
    till_payment(method=2, date="2027-10-01", amount=6000, reference="CHQ-0900")

    admin_page.goto(f"{module_url}/index.html?period=2028-01&state=todo", wait_until="domcontentloaded")
    expect(admin_page.locator("table.list tbody tr", has_text="CHQ-0900")).to_have_count(1)
    expect(admin_page.locator(f"{PERIODS} li.current")).to_contain_text("Janv")


def test_a_past_month_with_a_backlog_is_flagged(admin_page: Page, module_url, reseed):
    """CHQ-0140 is still to be collected for July 2026: the month carries the count,
    and clicking it lands on exactly those cheques. Nobody reopens a past month on
    their own, so the view has to say it."""
    reseed()
    admin_page.goto(f"{module_url}/index.html?period=all&state=todo", wait_until="domcontentloaded")

    late = admin_page.locator(f'{PERIODS} a[href*="period=2026-07"]', has_text="⚠1")
    expect(late).to_have_count(1)
    late.click()
    admin_page.wait_for_load_state("domcontentloaded")

    assert "period=2026-07" in admin_page.url
    expect(admin_page.locator("table.list tbody tr")).to_have_count(1)
    expect(admin_page.locator("table.list")).to_contain_text("CHQ-0140")

    # No marker on a month that is not behind: December is in the future, and
    # July stops being flagged once its cheque is on a slip.
    expect(admin_page.locator(f'{PERIODS} a[href*="period=2026-12"]', has_text="⚠")).to_have_count(0)


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


@pytest.mark.parametrize("label", ["Export CSV", "Export LibreOffice", "Export Excel"])
def test_the_three_export_formats_download(admin_page: Page, module_url, reseed, label):
    reseed()
    admin_page.goto(f"{module_url}/index.html", wait_until="domcontentloaded")

    admin_page.get_by_text("Exporter", exact=True).click()  # opens the export menu
    with admin_page.expect_download() as caught:
        admin_page.get_by_role("link", name=label).click()
    assert caught.value.path().stat().st_size > 0


def test_export_downloads_a_spreadsheet(admin_page: Page, module_url, reseed):
    """Every cheque, every column, no filter: it exists to be opened in a
    spreadsheet, where filtering is trivial."""
    reseed()
    admin_page.goto(f"{module_url}/index.html", wait_until="domcontentloaded")

    admin_page.get_by_text("Exporter", exact=True).click()
    with admin_page.expect_download() as caught:
        admin_page.get_by_role("link", name="Export LibreOffice").click()
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
