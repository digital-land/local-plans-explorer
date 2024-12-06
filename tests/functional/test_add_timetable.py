from flask import url_for
from playwright.sync_api import expect


def test_timetable_links(live_server, page, test_data):
    page.goto(
        url_for(
            "local_plan.get_plan", reference="some-where-local-plan", _external=True
        )
    )
    page.get_by_role("link", name="✚ Add event").click()
    page.get_by_label("Local plan event type").click()
    page.get_by_label("Local plan event type").select_option("timetable-published")
    page.get_by_label("Year").click()
    page.get_by_label("Year").fill("2025")
    page.get_by_label("Notes").click()
    page.get_by_label("Notes").fill("Some notes about this")
    page.get_by_role("button", name="Save").click()
    page.get_by_role("cell", name="Local development scheme").click()
    expect(page.locator("tbody")).to_contain_text("Local development scheme published")
    page.get_by_role("cell", name="2025").click()
    expect(page.locator("tbody")).to_contain_text("2025")
    expect(page.locator("h1")).to_contain_text("Somewhere Local Plan")

    # edit the date
    page.get_by_role("link", name="Edit", exact=True).click()
    page.get_by_label("Day").click()
    page.get_by_label("Day").fill("12")
    page.get_by_label("Month").click()
    page.get_by_label("Month").fill("12")
    page.get_by_role("button", name="Save").click()
    expect(page.locator("h1")).to_contain_text("Somewhere Local Plan")
    expect(page.locator("tbody")).to_contain_text("2025-12-12")
