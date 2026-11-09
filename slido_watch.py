import os, sys, time, requests
from playwright.sync_api import sync_playwright

SERVER = "https://ntfy-me.com"
TOPIC = os.environ["NTFY_TOPIC"]
code = sys.argv[1].strip().lstrip("#")
DURATION = 90 * 60

def notify(msg):
    try:
        requests.post(f"{SERVER}/{TOPIC}", data=msg.encode(), timeout=10)
    except Exception as e:
        print("ntfy failed:", e, flush=True)

# Runs inside the page: counts every time the "Poll has been activated" alert appears
INSTALL_JS = """
() => {
  if (window.__w) return;
  window.__w = {fired: 0};
  new MutationObserver(muts => {
    for (const m of muts) {
      const txt = (m.target.textContent || '') + Array.from(m.addedNodes).map(n => n.textContent || '').join('');
      if (txt.includes('Poll has been activated')) window.__w.fired++;
    }
  }).observe(document.documentElement, {childList: true, subtree: true, characterData: true});
}
"""

PANEL_OPEN_JS = """
() => {
  const p = document.querySelector('#live-tabpanel-polls');
  return !!p && !p.hidden && p.children.length > 0;
}
"""

PAGE_READY_JS = "() => !!document.querySelector('#live-tabpanel-questions, #live-tabpanel-polls')"

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    )
    page = ctx.new_page()

    def load():
        resp = page.goto(f"https://app.sli.do/event/{code}", wait_until="domcontentloaded")
        print("HTTP status:", resp.status if resp else None, flush=True)
        try:
            page.wait_for_selector("#live-tabpanel-polls", state="attached", timeout=30000)
        except Exception:
            print("Panel not found after 30s", flush=True)
        print("Loaded:", page.url[:100], flush=True)
        print("Title:", page.title(), flush=True)
        try:
            print("Body:", page.inner_text("body")[:300].replace("\n", " | "), flush=True)
        except Exception as e:
            print("Body read failed:", e, flush=True)

    load()

    try:
        ready_at_start = page.evaluate(PAGE_READY_JS)
    except Exception:
        ready_at_start = False

    if ready_at_start:
        notify(f"Watching Slido {code} for 90 min")
    else:
        notify(f"Slido page failed to load for {code}, not watching yet")

    end = time.time() + DURATION
    last_open, last_fired = False, 0
    last_log, not_ready_since = 0, None

    while time.time() < end:
        try:
            page.evaluate(INSTALL_JS)
            ready = page.evaluate(PAGE_READY_JS)
            is_open = page.evaluate(PANEL_OPEN_JS)
            fired = page.evaluate("() => (window.__w ? window.__w.fired : 0)")
        except Exception as e:
            print("check failed:", e, flush=True)
            time.sleep(1)
            continue

        # Reload if the page never loaded properly
        if not ready:
            not_ready_since = not_ready_since or time.time()
            if time.time() - not_ready_since > 30:
                print("Page not ready for 30s, reloading", flush=True)
                load()
                not_ready_since = None
                last_open, last_fired = False, 0
                continue
        else:
            not_ready_since = None

        if (is_open and not last_open) or fired > last_fired:
            notify("New Slido poll!")
            print("POLL DETECTED", f"(panel_open={is_open}, alerts={fired})", flush=True)

        if is_open != last_open:
            print("State change: poll_open =", is_open, flush=True)

        last_open, last_fired = is_open, fired

        if time.time() - last_log > 15:
            print(f"alive | ready={ready} poll_open={is_open} alerts={fired}", flush=True)
            last_log = time.time()

        time.sleep(1)

    notify("Slido watcher finished")
