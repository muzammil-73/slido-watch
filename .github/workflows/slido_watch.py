import os, sys, time, requests
from playwright.sync_api import sync_playwright

TOPIC = os.environ["NTFY_TOPIC"]
code = sys.argv[1].strip().lstrip("#")
DURATION = 90 * 60

def notify(msg):
    try:
        requests.post(f"https://ntfy.sh/{TOPIC}", data=msg.encode(), timeout=10)
    except Exception as e:
        print("ntfy failed:", e)

with sync_playwright() as p:
    page = p.chromium.launch().new_page()
    page.goto(f"https://app.sli.do/event/{code}")
    page.wait_for_timeout(5000)
    print("Loaded:", page.url, "|", page.title())
    notify(f"Watching Slido {code} for 90 min")

    end, notified, last_log = time.time() + DURATION, False, 0
    while time.time() < end:
        try:
            has_poll = page.locator("#live-tabpanel-polls:not([hidden])").count() > 0
        except Exception as e:
            print("check failed:", e)
            has_poll = notified
        if has_poll and not notified:
            notify("New Slido poll!")
            print("POLL DETECTED")
        notified = has_poll
        if time.time() - last_log > 30:
            print(f"alive, poll_visible={has_poll}")
            last_log = time.time()
        time.sleep(2)
    notify("Slido watcher finished")
