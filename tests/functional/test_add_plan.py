from flask import url_for
from playwright.sync_api import expect


def test_add_plan(live_server, page):
    page.goto(url_for("main.index", _external=True))
    page.get_by_role("link", name="✚ Add new plan").click()
    page.get_by_label("Name of plan").click()
    page.get_by_label("Name of plan").fill("This is a test local plan")
    page.get_by_label("Name of plan").press("Tab")
    page.get_by_role("combobox", name="Organisation").fill("Somewhere Borough Council")
    page.get_by_role("option", name="Somewhere Borough Council", exact=True).click()
    page.get_by_label("Brief description of plan").click()
    page.get_by_label("Brief description of plan").fill(
        "This is a test local plan description"
    )
    page.get_by_label("Brief description of plan").press("Tab")
    page.get_by_label("URL for plan information").fill(
        "http://www.borough-council-local-plan.gov.uk"
    )
    page.locator("#period_start_date").click()
    page.locator("#period_start_date").fill("2024")
    page.locator("#period_end_date").click()
    page.locator("#period_end_date").fill("2034")
    page.get_by_role("button", name="Save").click()

    expect(page.locator("h1")).to_contain_text("Area covered by this plan")
    expect(page.locator("form")).to_contain_text(
        "Warning We don't have any boundaries for the authoring planning authorities. Please provide one."
    )
    page.get_by_role("link", name="Skip for now").click()

    expect(page.locator("h1")).to_contain_text("This is a test local plan")
    expect(page.locator("dl")).to_contain_text("Reference")
    expect(page.locator("dl")).to_contain_text("this-is-a-test-local-plan")
