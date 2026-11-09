import os, sys, time, requests
from playwright.sync_api import sync_playwright

SERVER = "https://ntfy-me.com"
TOPIC = os.environ["NTFY_TOPIC"]
code = sys.argv[1].strip()
URL = code if code.startswith("http") else f"https://app.sli.do/event/{code.lstrip('#')}"
DURATION = 90 * 60

def notify(msg, title="Slido watcher", priority="high"):
    try:
        requests.post(
            f"{SERVER}/{TOPIC}",
            data=msg.encode("utf-8"),
            headers={"Title": title, "Priority": priority},
            timeout=10,
        )
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

PANEL_TEXT_JS = """
() => {
  const p = document.querySelector('#live-tabpanel-polls');
  return (p && !p.hidden) ? p.innerText.replace(/\\s+/g, ' ').trim().slice(0, 150) : '';
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
        try:
            resp = page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            print("HTTP status:", resp.status if resp else None, flush=True)
