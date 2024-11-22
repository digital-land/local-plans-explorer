from flask import url_for
from playwright.sync_api import expect


def test_add_and_edit_document(live_server, page, test_data):
    # Start from the plan page
    page.goto(
        url_for(
            "local_plan.get_plan", reference="some-where-local-plan", _external=True
        )
    )

    # Add new document
    page.get_by_role("link", name="✚ add document").click()

    # Fill in document details
    page.get_by_label("Name of supporting document").fill("Test supporting document")
    page.get_by_label("Brief description of supporting document").fill(
        "This is a test document description"
    )
    page.get_by_label("URL for document information").fill(
        "http://www.borough-council-local-plan.gov.uk/doc-info"
    )
    page.get_by_label("Document URL").fill(
        "http://www.borough-council-local-plan.gov.uk/doc.pdf"
    )

    # Select organisation
    page.get_by_role("combobox", name="Organisation").fill("Somewhere Borough Council")
    page.get_by_role("option", name="Somewhere Borough Council", exact=True).click()

    # Select document type
    page.locator("#document_types-0").check()  # First checkbox in document types

    # Check "Ready for publication"
    page.locator("#for_publication").check()

    # Submit form
    page.get_by_role("button", name="Create document record").click()

    # Verify document was created
    expect(page.locator("h1")).to_contain_text(
        "Local plan document for Somewhere Local Plan"
    )
    expect(page.locator("dl")).to_contain_text("Reference")
    expect(page.locator("dl")).to_contain_text("test-supporting-document")

    # Edit document
    page.get_by_role("link", name="Edit").click()

    # Update document details
    page.get_by_label("Name of supporting document").fill("Updated test document")
    page.get_by_label("Brief description of supporting document").fill(
        "Updated description"
    )
    page.get_by_label("URL for document information").fill(
        "http://www.borough-council-local-plan.gov.uk/updated-info"
    )
    page.get_by_label("URL for document").fill(
        "http://www.borough-council-local-plan.gov.uk/updated.pdf"
    )

    # Change status to "For review"
    page.get_by_text("For review", exact=True).click()

    # Save changes
    page.get_by_role("button", name="Edit record").click()

    # Verify updates
    expect(page.locator("dl")).to_contain_text("Name")
    expect(page.locator("dl")).to_contain_text("Updated test document")
    expect(page.locator("section")).to_contain_text("For review")


def test_document_status_validation(live_server, page, test_data):
    page.goto(
        url_for(
            "local_plan.get_plan", reference="some-where-local-plan", _external=True
        )
    )

    # Add new document
    page.get_by_role("link", name="✚ add document").click()

    # Fill required fields
    page.get_by_label("Name of supporting document").fill("Status test document")
    page.get_by_label("Document URL").fill(
        "http://www.borough-council-local-plan.gov.uk/status-test.pdf"
    )
    page.get_by_role("combobox", name="Organisation").fill("Somewhere Borough Council")
    page.get_by_role("option", name="Somewhere Borough Council", exact=True).click()

    # Create document
    page.get_by_role("button", name="Create document record").click()

    # Edit document and try to change status
    page.get_by_role("link", name="Edit").click()
    page.get_by_text("For platform", exact=True).click()
    page.get_by_role("button", name="Edit record").click()

    # Verify error message
    expect(
        page.get_by_text(
            "Can't set status to 'For platform' as the local plan status is 'For review'"
        )
    ).to_be_visible()


def test_document_url_validation(live_server, page, test_data):
    page.goto(
        url_for(
            "local_plan.get_plan", reference="some-where-local-plan", _external=True
        )
    )

    # Add new document
    page.get_by_role("link", name="✚ add document").click()

    # Test invalid URL
    page.get_by_label("Name of supporting document").fill("URL test document")
    page.get_by_label("Document URL").fill("not-a-valid-url")
    page.get_by_role("combobox", name="Organisation").fill("Somewhere Borough Council")
    page.get_by_role("option", name="Somewhere Borough Council", exact=True).click()

    # Try to submit
    page.get_by_role("button", name="Create document record").click()

    # Verify URL validation error
    expect(page.locator("#document_url-error")).to_contain_text(
        "Error: Invalid URL. Error: URL must start with http or https"
    )
