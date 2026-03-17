from playwright.sync_api import Page, expect, sync_playwright
import json
import time

def capture_dashboard(page: Page):
    # Navigate to the dashboard
    page.goto("http://localhost:8000")

    # Wait for the status to become "Live" (connected via WebSocket)
    expect(page.locator("#status")).to_have_text("Live", timeout=10000)

    # Wait a bit for the metrics and chart to populate
    time.sleep(2)

    # Take screenshot of the dashboard
    page.screenshot(path="screenshots/dashboard.png", full_page=True)
    print("Dashboard screenshot saved.")

def capture_api_responses(page: Page):
    # Capture /api/last
    page.goto("http://localhost:8000/api/last")
    pre = page.locator("pre")
    content = pre.inner_text()
    with open("screenshots/api_last.json", "w") as f:
        f.write(content)
    page.screenshot(path="screenshots/api_last.png")
    print("API /api/last captured.")

    # Capture /api/history
    page.goto("http://localhost:8000/api/history?limit=5")
    pre = page.locator("pre")
    content = pre.inner_text()
    with open("screenshots/api_history.json", "w") as f:
        f.write(content)
    page.screenshot(path="screenshots/api_history.png")
    print("API /api/history captured.")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            capture_dashboard(page)
            capture_api_responses(page)
        finally:
            browser.close()
