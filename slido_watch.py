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


INSTALL_JS = "() => { if (window.__w) return; window.__w = {fired: 0}; new MutationObserver(muts => { for (const m of muts) { const txt = (m.target.textContent || '') + Array.from(m.addedNodes).map(n => n.textContent || '').join(''); if (txt.includes('Poll has been activated')) window.__w.fired++; } }).observe(document.documentElement, {childList: true, subtree: true, characterData: true}); }"

PANEL_OPEN_JS = "() => { const p = document.querySelector('#live-tabpanel-polls'); return !!p && !p.hidden && p.children.length > 0; }"

PANEL_TEXT_JS = "() => { const p = document.querySelector('#live-tabpanel-polls'); return (p && !p.hidden) ? p.innerText : ''; }"

PAGE_READY_JS = "() => !!document.querySelector('#live-tabpanel-questions, #live-tabpanel-polls')"

FIRED_JS = "() => (window.__w ? window.__w.fired : 0)"


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        )
        page = ctx.new_page()

        def load():
            try:
                resp = page.goto(URL, wait_until="domcontentloaded", timeout=60000)
                status = resp.status if resp else None
                print("HTTP status:", status, flush=True)
            except Exception as e:
                print("goto failed:", e, flush=True)
            try:
                page.wait_for_selector("#live-tabpanel-polls", state="attached", timeout=45000)
            except Exception:
                print("Panel not found after 45s", flush=True)
            print("Loaded:", page.url[:120], flush=True)
            try:
                print("Title:", page.title(), flush=True)
            except Exception:
                pass
            body = ""
            try:
                body = page.inner_text("body")[:300].replace("\n", " | ")
            except Exception as e:
                print("Body read failed:", e, flush=True)
            print("Body:", body, flush=True)
            return body

        body = load()

        if "Event not found" in body:
            notify("Slido says 'Event not found'. Paste the full app.sli.do URL from your browser's address bar.",
                   title="Slido watcher error")
            browser.close()
            sys.exit(1)

        try:
            announced = page.evaluate(PAGE_READY_JS)
        except Exception:
            announced = False

        if announced:
            notify("Watching for polls for 90 min", title="Slido watcher started")
        else:
            notify("Page didn't load yet, retrying...", title="Slido watcher", priority="default")

        end = time.time() + DURATION
        last_open = False
        last_fired = 0
        last_log = 0
        not_ready_since = None
        reloads = 0
        warned = False

        while time.time() < end:
            try:
                page.evaluate(INSTALL_JS)
                ready = page.evaluate(PAGE_READY_JS)
                is_open = page.evaluate(PANEL_OPEN_JS)
                fired = page.evaluate(FIRED_JS)
            except Exception as e:
                print("check failed:", e, flush=True)
                time.sleep(1)
                continue

            if not ready:
                if not_ready_since is None:
                    not_ready_since = time.time()
                if time.time() - not_ready_since > 30:
                    print("Page not ready for 30s, reloading", flush=True)
                    body = load()
                    reloads += 1
                    not_ready_since = None
                    last_open = False
                    last_fired = 0
                    if "Event not found" in body:
                        notify("Slido says 'Event not found'. Check the URL.", title="Slido watcher error")
                        break
                    if reloads >= 3 and not warned:
                        notify("Can't load the Slido page. Check the GitHub log.", title="Slido watcher error")
                        warned = True
                    continue
            else:
                not_ready_since = None
                if not announced:
                    notify("Page loaded, now watching for polls", title="Slido watcher started")
                    announced = True

            if (is_open and not last_open) or fired > last_fired:
                time.sleep(0.5)
                try:
                    text = " ".join(page.evaluate(PANEL_TEXT_JS).split())[:150]
                except Exception:
                    text = ""
                notify(text or "A poll just opened", title="New Slido poll!", priority="urgent")
                print("POLL DETECTED", "panel_open=" + str(is_open), "alerts=" + str(fired), text, flush=True)

            if is_open != last_open:
                print("State change: poll_open =", is_open, flush=True)

            last_open = is_open
            last_fired = fired

            if time.time() - last_log > 15:
                print("alive | ready=" + str(ready), "poll_open=" + str(is_open), "alerts=" + str(fired), flush=True)
                last_log = time.time()

            time.sleep(1)

        notify("Watcher finished", title="Slido watcher", priority="low")
        browser.close()


run()
