import os
import time
import random
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BASE_URL = "https://www.amazon.in"

UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(UTILS_DIR, "amazon_products.csv")
PROFILE_DIR = os.path.join(UTILS_DIR, "amazon_chrome_profile")
DEBUG_DIR = os.path.join(UTILS_DIR, "debug_amazon")


def _ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)


def _append_row(row: dict) -> None:
    df = pd.DataFrame([row])
    if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
        df.to_csv(CSV_FILE, mode="a", index=False, header=False, encoding="utf-8")
    else:
        df.to_csv(CSV_FILE, index=False, encoding="utf-8")


def _human_pause(a=0.8, b=2.0):
    time.sleep(random.uniform(a, b))


def _normalize_query(q: str) -> str:
    # coffee_table -> coffee table, console_table -> console table
    q = (q or "").strip()
    q = q.replace("_", " ")
    q = " ".join(q.split())
    return q


def _best_effort_close_popups(page):
    for sel in [
        "input#sp-cc-accept",
        "button:has-text('Accept')",
        "button:has-text('I Agree')",
        "button:has-text('Continue')",
    ]:
        try:
            if page.locator(sel).count() > 0:
                page.locator(sel).first.click(timeout=1500)
                _human_pause(0.3, 0.8)
        except Exception:
            pass

    for sel in ["button[aria-label='Close']", "button.a-button-close", "span.a-button-close"]:
        try:
            if page.locator(sel).count() > 0:
                page.locator(sel).first.click(timeout=1500)
                _human_pause(0.3, 0.8)
        except Exception:
            pass


def _dump_debug(page, tag: str, product_name: str):
    _ensure_dir(DEBUG_DIR)
    stamp = int(time.time())
    png = os.path.join(DEBUG_DIR, f"{tag}_{product_name}_{stamp}.png")
    html = os.path.join(DEBUG_DIR, f"{tag}_{product_name}_{stamp}.html")
    try:
        page.screenshot(path=png, full_page=True)
    except Exception:
        pass
    try:
        with open(html, "w", encoding="utf-8") as f:
            f.write(page.content())
    except Exception:
        pass
    print(f"[DEBUG] Saved: {png}")
    print(f"[DEBUG] Saved: {html}")


def _wait_for_results_container(page) -> bool:
    candidates = [
        "div.s-main-slot",
        "span[data-component-type='s-search-results']",
        "div[data-component-type='s-search-result']",
    ]
    for sel in candidates:
        try:
            page.wait_for_selector(sel, timeout=15000)
            return True
        except PlaywrightTimeoutError:
            continue
    return False


def _is_valid_product_href(href: str) -> bool:
    if not href:
        return False
    h = href.lower()
    # reject sponsored / tracking / ads
    if "sspa" in h or "/sspa/" in h or "sspa/click" in h:
        return False
    if "gp/slredirect" in h or "slredirect" in h:
        return False
    if "click" in h and "ref=" in h and "amazon" in h:
        return False
    # accept typical product patterns
    return ("/dp/" in h) or ("/gp/" in h and "/product" in h) or ("/dp%2f" in h)


def _pick_first_valid_product_href(page) -> str | None:
    """
    Amazon markup varies. We will:
      1) iterate result blocks
      2) look for title link anchors (a-text-normal / s-link-style)
      3) pick the first href that looks like a real product page (not sponsored)
    """
    blocks = page.locator("div[data-component-type='s-search-result']")
    n = blocks.count()
    if n == 0:
        return None

    # Try first ~15 blocks
    limit = min(n, 15)
    for i in range(limit):
        b = blocks.nth(i)

        # Title link variants seen in your HTML:
        candidates = [
            "a.a-link-normal.s-link-style.a-text-normal",
            "a.a-link-normal.s-line-clamp-2.s-link-style.a-text-normal",
            "h2 a.a-link-normal",  # keep old fallback
        ]

        for sel in candidates:
            a = b.locator(sel).first
            if a.count() == 0:
                continue
            href = a.get_attribute("href") or ""
            if _is_valid_product_href(href):
                # convert to absolute if needed
                if href.startswith("/"):
                    return BASE_URL + href
                return href

        # image link fallback (sometimes exists even if title selector changes)
        img_a = b.locator("a.a-link-normal.s-no-outline").first
        if img_a.count() > 0:
            href = img_a.get_attribute("href") or ""
            if _is_valid_product_href(href):
                if href.startswith("/"):
                    return BASE_URL + href
                return href

    return None


def _extract_title(page) -> str:
    if page.locator("span#productTitle").count() > 0:
        return page.locator("span#productTitle").first.inner_text().strip()
    if page.locator("input#productTitle").count() > 0:
        v = page.locator("input#productTitle").first.get_attribute("value") or ""
        return v.strip()
    return ""


def _extract_main_image(page) -> str:
    if page.locator("#landingImage").count() > 0:
        return (page.locator("#landingImage").first.get_attribute("src") or "").strip()
    if page.locator("#imgTagWrapperId img").count() > 0:
        return (page.locator("#imgTagWrapperId img").first.get_attribute("src") or "").strip()
    if page.locator("img[data-old-hires]").count() > 0:
        return (page.locator("img[data-old-hires]").first.get_attribute("data-old-hires") or "").strip()
    return ""


def scrape_amazon_browser(product_name: str, max_products: int = 1, user_data_dir: str = None) -> None:
    if max_products != 1:
        raise ValueError("Currently only max_products=1 is supported in this browser scraper.")

    if user_data_dir is None:
        user_data_dir = PROFILE_DIR

    _ensure_dir(DEBUG_DIR)

    query = _normalize_query(product_name)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="chrome",
            headless=False,
            viewport={"width": 1366, "height": 768},
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = context.new_page()

        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        _human_pause(1.0, 2.0)
        _best_effort_close_popups(page)

        if page.locator("input#twotabsearchtextbox").count() == 0:
            print(f"[WARN] Search box not found for '{product_name}'. URL={page.url}")
            _dump_debug(page, "no_searchbox", product_name)
            context.close()
            return

        page.fill("input#twotabsearchtextbox", query)
        _human_pause(0.2, 0.6)
        page.press("input#twotabsearchtextbox", "Enter")
        page.wait_for_load_state("domcontentloaded", timeout=60000)
        _human_pause(1.0, 2.0)
        _best_effort_close_popups(page)

        if not _wait_for_results_container(page):
            print(f"[WARN] Results container not detected for '{product_name}'. URL={page.url} TITLE={page.title()}")
            _dump_debug(page, "no_results_container", product_name)
            context.close()
            return

        product_url = _pick_first_valid_product_href(page)
        if not product_url:
            print(f"[WARN] No product link found for '{product_name}'. URL={page.url} TITLE={page.title()}")
            _dump_debug(page, "no_links", product_name)
            context.close()
            return

        # Open product URL directly (more reliable than click)
        page.goto(product_url, wait_until="domcontentloaded", timeout=60000)
        _human_pause(1.0, 2.0)
        _best_effort_close_popups(page)

        title = _extract_title(page)
        image_url = _extract_main_image(page)

        row = {
            "product_type": product_name,
            "product_title": title,
            "product_url": page.url,
            "product_images": image_url,
            "image_count": 1 if image_url else 0,
            "product_dimensions": "",
        }

        _append_row(row)
        print(f"[OK] Saved 1 product for '{product_name}' -> {CSV_FILE}")

        context.close()


if __name__ == "__main__":
    product = input("Enter product name: ").strip()
    if product:
        scrape_amazon_browser(product_name=product, max_products=1)
    else:
        print("No product entered.")