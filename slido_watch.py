import os, sys, time, requests
from playwright.sync_api import sync_playwright

SERVER = "https://ntfy-me.com"
TOPIC = os.environ["NTFY_TOPIC"]
code = sys.argv[1].strip()
if code.startswith("http"):
    URL = code
else:
    URL = "https://app.sli.do/event/" + code.lstrip("#")
DURATION = 90 * 60


def notify(msg, title="Slido watcher", priority="high"):
    try:
        requests.post(
            SERVER + "/" + TOPIC,
            data=msg.encode("utf-8"),
            headers={"Title": title, "Priority": priority},
            timeout=10,
        )
    except Exception as e:
        print("ntfy failed:", e, flush=True)


INSTALL_JS = """
() => {
  if (window.__w) return;
  window.__w = {fired: 0};
  new MutationObserver(muts => {
    for (const m of muts) {
      const txt = (m.target.textContent || '') + Array.from(m.addedNodes).map(n => n.textContent || '').join('');
      if (txt.includes('Poll has been activated')) window.__w.fired++;
    }
