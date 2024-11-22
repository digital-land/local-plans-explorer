from flask import url_for
from playwright.sync_api import expect


def test_timetable_links(live_server, page, test_data):
    page.goto(
        url_for(
            "local_plan.get_plan", reference="some-where-local-plan", _external=True
        )
    )

    page.get_by_text("Regulation 18").first.click()
    expect(page.locator("#main-content")).to_contain_text("Estimated dates")
    expect(page.locator("#main-content")).to_contain_text("Regulation 18")
    page.get_by_role("link", name="Skip to next event").click()

    expect(page.locator("#main-content")).to_contain_text("Estimated dates")
    expect(page.locator("#main-content")).to_contain_text("Regulation 19")
    page.get_by_role("link", name="Skip to next event").click()

    expect(page.locator("#main-content")).to_contain_text("Estimated dates")
    expect(page.locator("#main-content")).to_contain_text("Examination and adoption")
    page.get_by_role("link", name="Return to local plan").click()

    expect(page.locator("h1")).to_contain_text("Somewhere Local Plan")


def test_add_estimated_dates(live_server, page, test_data):
    page.goto(
        url_for(
            "local_plan.get_plan", reference="some-where-local-plan", _external=True
        )
    )
    page.get_by_text("Regulation 18").first.click()
    page.get_by_role("group", name="Draft local plan published").get_by_label(
        "Year"
    ).click()
    page.get_by_role("group", name="Draft local plan published").get_by_label(
        "Year"
    ).fill("2024")
    page.get_by_role("group", name="Regulation 18 consultation start").get_by_label(
        "Year"
    ).click()
    page.get_by_role("group", name="Regulation 18 consultation start").get_by_label(
        "Year"
    ).fill("2025")
    page.locator("#estimated_reg_18_public_consultation_end div").filter(
        has_text="Year"
    ).nth(1).click()
    page.get_by_role("group", name="Regulation 18 consultation end").get_by_label(
        "Year"
    ).click()
    page.get_by_role("group", name="Regulation 18 consultation end").get_by_label(
        "Year"
    ).fill("2026")
    page.get_by_role("button", name="Save").click()
    expect(page.locator("dl")).to_contain_text("Draft local plan published")
    page.get_by_text("2024").click()
    expect(page.locator("dl")).to_contain_text("2024")
    expect(page.locator("dl")).to_contain_text("Consultation period")
    expect(page.locator("dl")).to_contain_text("Consultation period 2025 - 2026")
    page.get_by_role("link", name="Continue").click()
    page.get_by_role("group", name="Publication local plan").get_by_label("Day").click()
    page.get_by_role("group", name="Publication local plan").get_by_label("Day").fill(
        "1"
    )
    page.get_by_role("group", name="Publication local plan").get_by_label(
        "Month"
    ).click()
    page.get_by_role("group", name="Publication local plan").get_by_label("Month").fill(
        "2"
    )
    page.get_by_role("group", name="Publication local plan").get_by_label(
        "Year"
    ).click()
    page.get_by_role("group", name="Publication local plan").get_by_label("Year").fill(
        "2026"
    )
    page.get_by_role("group", name="Regulation 19 consultation start").get_by_label(
        "Month"
    ).click()
    page.get_by_role("group", name="Regulation 19 consultation start").get_by_label(
        "Month"
    ).fill("6")
    page.get_by_role("group", name="Regulation 19 consultation start").get_by_label(
        "Year"
    ).click()
    page.get_by_role("group", name="Regulation 19 consultation start").get_by_label(
        "Year"
    ).fill("2026")
    page.get_by_role("group", name="Regulation 19 consultation end").get_by_label(
        "Month"
    ).click()
    page.get_by_role("group", name="Regulation 19 consultation end").get_by_label(
        "Month"
    ).fill("3")
    page.get_by_role("group", name="Regulation 19 consultation end").get_by_label(
        "Year"
    ).click()
    page.get_by_role("group", name="Regulation 19 consultation end").get_by_label(
        "Year"
    ).fill("2027")
    page.get_by_role("button", name="Save").click()
    expect(page.locator("dl")).to_contain_text("Publication local plan published")
    expect(page.locator("dl")).to_contain_text("1/2/2026")
    expect(page.locator("dl")).to_contain_text("Consultation period 6/2026 - 3/2027")
    page.get_by_role("link", name="Continue").click()
    page.get_by_role("group", name="Submit plan for examination").get_by_label(
        "Year"
    ).click()
    page.get_by_role("group", name="Submit plan for examination").get_by_label(
        "Year"
    ).fill("2027")
    page.get_by_role("group", name="Adoption of local plan").get_by_label(
        "Year"
    ).click()
    page.get_by_role("group", name="Adoption of local plan").get_by_label("Year").fill(
        "2030"
    )
    page.get_by_role("button", name="Save").click()
    expect(page.locator("dl")).to_contain_text("Submit plan for examination")
    expect(page.locator("dl")).to_contain_text("2027")
    expect(page.locator("dl")).to_contain_text("Adoption of local plan")
    expect(page.locator("dl")).to_contain_text("2030")
    page.get_by_role("link", name="Close").click()
    expect(page.locator("h1")).to_contain_text("Somewhere Local Plan")


def test_add_actual_dates(live_server, page, test_data):
    page.goto(
        url_for(
            "local_plan.get_plan", reference="some-where-local-plan", _external=True
        )
    )
    page.get_by_role("link", name="Regulation").nth(2).click()
    expect(page.locator("#main-content")).to_contain_text("Actual dates")
    page.get_by_role("group", name="Draft local plan published").get_by_label(
        "Day"
    ).click()
    page.get_by_role("group", name="Draft local plan published").get_by_label(
        "Day"
    ).fill("1")
    page.get_by_role("group", name="Draft local plan published").get_by_label(
        "Day"
    ).press("Tab")
    page.get_by_role("group", name="Draft local plan published").get_by_label(
        "Month"
    ).fill("2")
    page.get_by_role("group", name="Draft local plan published").get_by_label(
        "Month"
    ).press("Tab")
    page.get_by_role("group", name="Draft local plan published").get_by_label(
        "Year"
    ).fill("2025")
    page.get_by_role("group", name="Draft local plan published").get_by_label(
        "Year"
    ).press("Tab")
    page.get_by_role("group", name="Regulation 18 consultation start").get_by_label(
        "Day"
    ).fill("2")
    page.get_by_role("group", name="Regulation 18 consultation start").get_by_label(
        "Day"
    ).press("Tab")
    page.get_by_role("group", name="Regulation 18 consultation start").get_by_label(
        "Month"
    ).fill("3")
    page.get_by_role("group", name="Regulation 18 consultation start").get_by_label(
        "Month"
    ).press("Tab")
    page.get_by_role("group", name="Regulation 18 consultation start").get_by_label(
        "Year"
    ).fill("2026")
    page.get_by_role("group", name="Regulation 18 consultation start").get_by_label(
        "Year"
    ).press("Tab")
    page.get_by_role("group", name="Regulation 18 consultation end").get_by_label(
        "Day"
    ).fill("4")
    page.get_by_role("group", name="Regulation 18 consultation end").get_by_label(
        "Day"
    ).press("Tab")
    page.get_by_role("group", name="Regulation 18 consultation end").get_by_label(
        "Month"
    ).fill("5")
    page.get_by_role("group", name="Regulation 18 consultation end").get_by_label(
        "Month"
    ).press("Tab")
    page.get_by_role("group", name="Regulation 18 consultation end").get_by_label(
        "Year"
    ).fill("2027")
    page.get_by_role("button", name="Save").click()
    expect(page.locator("dl")).to_contain_text("Draft local plan published")
    expect(page.locator("dl")).to_contain_text("1/2/2025")
    expect(page.locator("dl")).to_contain_text("Consultation period")
    expect(page.locator("dl")).to_contain_text(
        "Consultation period 2/3/2026 - 4/5/2027"
    )
    page.get_by_role("link", name="Continue").click()
    page.get_by_role("heading", name="Regulation 19", exact=True).click()
    expect(page.locator("#main-content")).to_contain_text("Regulation 19")
    page.get_by_role("group", name="Publication local plan").get_by_label("Day").click()
    page.get_by_role("group", name="Publication local plan").get_by_label("Day").fill(
        "6"
    )
    page.get_by_role("group", name="Publication local plan").get_by_label("Day").press(
        "Tab"
    )
    page.get_by_role("group", name="Publication local plan").get_by_label("Month").fill(
        "7"
    )
    page.get_by_role("group", name="Publication local plan").get_by_label(
        "Month"
    ).press("Tab")
    page.get_by_role("group", name="Publication local plan").get_by_label("Year").fill(
        "2028"
    )
    page.get_by_role("group", name="Publication local plan").get_by_label("Year").press(
        "Tab"
    )
    page.get_by_role("group", name="Regulation 19 consultation start").get_by_label(
        "Day"
    ).fill("8")
    page.get_by_role("group", name="Regulation 19 consultation start").get_by_label(
        "Day"
    ).press("Tab")
    page.get_by_role("group", name="Regulation 19 consultation start").get_by_label(
        "Month"
    ).fill("9")
    page.get_by_role("group", name="Regulation 19 consultation start").get_by_label(
        "Month"
    ).press("Tab")
    page.get_by_role("group", name="Regulation 19 consultation start").get_by_label(
        "Year"
    ).fill("2029")
    page.get_by_role("group", name="Regulation 19 consultation start").get_by_label(
        "Year"
    ).press("Tab")
    page.get_by_role("group", name="Regulation 19 consultation end").get_by_label(
        "Day"
    ).fill("10")
    page.get_by_role("group", name="Regulation 19 consultation end").get_by_label(
        "Day"
    ).press("Tab")
    page.get_by_role("group", name="Regulation 19 consultation end").get_by_label(
        "Month"
    ).fill("11")
    page.get_by_role("group", name="Regulation 19 consultation end").get_by_label(
        "Month"
    ).press("Tab")
    page.get_by_role("group", name="Regulation 19 consultation end").get_by_label(
        "Year"
    ).fill("2030")
    page.get_by_role("button", name="Save").click()
    expect(page.locator("dl")).to_contain_text("Publication local plan published")
    expect(page.locator("dl")).to_contain_text("6/7/2028")
    expect(page.locator("dl")).to_contain_text("Consultation period")
    expect(page.locator("dl")).to_contain_text(
        "Consultation period 8/9/2029 - 10/11/2030"
    )
    page.get_by_role("link", name="Continue").click()
    expect(page.locator("#main-content")).to_contain_text(
        "Planning inspectorate examination"
    )
    page.get_by_role("group", name="Plan submitted").get_by_label("Day").click()
    page.get_by_role("group", name="Plan submitted").get_by_label("Day").fill("12")
    page.get_by_role("group", name="Plan submitted").get_by_label("Day").press("Tab")
    page.get_by_role("group", name="Plan submitted").get_by_label("Month").fill("1")
    page.get_by_role("group", name="Plan submitted").get_by_label("Month").press("Tab")
    page.get_by_role("group", name="Plan submitted").get_by_label("Year").fill("2030")
    page.get_by_role("group", name="Plan submitted").get_by_label("Year").press("Tab")
    page.get_by_role("group", name="Examination start date").get_by_label("Day").fill(
        "13"
    )
    page.get_by_role("group", name="Examination start date").get_by_label("Day").press(
        "Tab"
    )
    page.get_by_role("group", name="Examination start date").get_by_label("Month").fill(
        "2"
    )
    page.get_by_role("group", name="Examination start date").get_by_label(
        "Month"
    ).press("Tab")
    page.get_by_role("group", name="Examination start date").get_by_label("Year").fill(
        "2040"
    )
    page.get_by_role("group", name="Examination start date").get_by_label("Year").press(
        "Tab"
    )
    page.get_by_role("group", name="Examination end date").get_by_label("Day").fill(
        "14"
    )
    page.get_by_role("group", name="Examination end date").get_by_label("Day").press(
        "Tab"
    )
    page.get_by_role("group", name="Examination end date").get_by_label("Month").fill(
        "3"
    )
    page.get_by_role("group", name="Examination end date").get_by_label("Month").press(
        "Tab"
    )
    page.get_by_role("group", name="Examination end date").get_by_label("Year").fill(
        "2050"
    )
    page.get_by_role("button", name="Save").click()

    expect(page.locator("h1")).to_contain_text("Planning inspectorate examination")
    expect(page.locator("section")).to_contain_text("Submit plan for examination")
    expect(page.locator("section")).to_contain_text("12/1/2030")
    expect(page.locator("section")).to_contain_text(
        "Planning inspectorate examination start"
    )
    expect(page.locator("section")).to_contain_text("13/2/2040")
    expect(page.locator("section")).to_contain_text(
        "Planning inspectorate examination end"
    )
    expect(page.locator("section")).to_contain_text("14/3/2050")

    page.get_by_role("link", name="Continue").click()
    page.get_by_role("group", name="Planning inspectorate found").get_by_label(
        "Day"
    ).click()
    page.get_by_role("group", name="Planning inspectorate found").get_by_label(
        "Day"
    ).fill("15")
    page.get_by_role("group", name="Planning inspectorate found").get_by_label(
        "Day"
    ).press("Tab")
    page.get_by_role("group", name="Planning inspectorate found").get_by_label(
        "Month"
    ).fill("4")
    page.get_by_role("group", name="Planning inspectorate found").get_by_label(
        "Month"
    ).press("Tab")
    page.get_by_role("group", name="Planning inspectorate found").get_by_label(
        "Year"
    ).fill("2060")
    page.get_by_role("group", name="Planning inspectorate found").get_by_label(
        "Year"
    ).press("Tab")
    page.get_by_role("group", name="Report published").get_by_label("Day").fill("16")
    page.get_by_role("group", name="Report published").get_by_label("Day").press("Tab")
    page.get_by_role("group", name="Report published").get_by_label("Month").fill("5")
    page.get_by_role("group", name="Report published").get_by_label("Month").press(
        "Tab"
    )
    page.get_by_role("group", name="Report published").get_by_label("Year").fill("2070")
    page.get_by_role("button", name="Save").click()
    expect(page.locator("h1")).to_contain_text("Planning inspectorate findings")
    expect(page.locator("section")).to_contain_text("Planning inspectorate found sound")
    expect(page.locator("section")).to_contain_text("15/4/2060")
    expect(page.locator("section")).to_contain_text(
        "Planning inspectorate report published"
    )
    expect(page.locator("section")).to_contain_text("16/5/2070")
    page.get_by_role("link", name="Continue").click()
    expect(page.locator("h1")).to_contain_text("Somewhere Local Plan")
