from playwright.sync_api import sync_playwright, expect
import os
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # 1. Dashboard Light Mode
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        page.goto("http://localhost:8000")
        # Set theme to light
        page.evaluate("setTheme('light')")
        time.sleep(2) # Wait for charts and metrics
        page.screenshot(path="screenshots/dashboard_light.png")
        print("Captured dashboard_light.png")

        # 2. Dashboard Dark Mode
        page.evaluate("setTheme('dark')")
        time.sleep(1)
        page.screenshot(path="screenshots/dashboard_dark.png")
        print("Captured dashboard_dark.png")

        # 3. Add Chart Modal
        page.click("#addChartBtn")
        time.sleep(0.5)
        # We want the modal to be visible
        expect(page.locator("#addChartModal")).not_to_have_class("hidden")
        # Take a screenshot focusing on the modal area if possible, or just the whole page
        page.screenshot(path="screenshots/add_chart_modal.png")
        print("Captured add_chart_modal.png")
        page.click("#cancelChartBtn")

        # 4. Dashboard Mobile View
        mobile_context = browser.new_context(
            viewport={'width': 390, 'height': 844},
            is_mobile=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
        )
        mobile_page = mobile_context.new_page()
        mobile_page.goto("http://localhost:8000")
        mobile_page.evaluate("setTheme('light')")
        time.sleep(2)
        mobile_page.screenshot(path="screenshots/dashboard_mobile.png", full_page=True)
        print("Captured dashboard_mobile.png")

        # 5. Dashboard with Gauge (Default dashboard has a gauge for battery_voltage)
        # I'll just make sure we see it clearly.
        page.goto("http://localhost:8000")
        page.evaluate("setTheme('light')")
        time.sleep(2)
        # Scroll to the gauge if necessary, or just take full page
        # The default gauge is in 'charts-container'
        page.screenshot(path="screenshots/dashboard_with_gauge.png", full_page=True)
        print("Captured dashboard_with_gauge.png")

        browser.close()

if __name__ == "__main__":
    os.makedirs("screenshots", exist_ok=True)
    run()
