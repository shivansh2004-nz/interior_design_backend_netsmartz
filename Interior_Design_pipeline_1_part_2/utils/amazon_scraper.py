# import requests
# from bs4 import BeautifulSoup
# import pandas as pd
# import time
# import random
# from urllib.parse import quote
# import os
# import json

# import sys
# try:
#     sys.stdout.reconfigure(encoding="utf-8")
# except Exception:
#     pass

# HEADERS = {
#     "User-Agent": (
#         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#         "AppleWebKit/537.36 (KHTML, like Gecko) "
#         "Chrome/121.0.0.0 Safari/537.36"
#     ),
#     "Accept-Language": "en-IN,en;q=0.9"
# }
# BASE_URL = "https://www.amazon.in"


# def clean_text(text):
#     if not text:
#         return ""
#     return (
#         text.replace("\u200e", "")
#             .replace("\u200f", "")
#             .replace("\xa0", " ")
#             .strip()
#     )


# def extract_seller_images(soup):
#     """
#     Extract ONLY seller-uploaded product images
#     (No customer review images)
#     """
#     image_urls = set()

#     # Primary image block (seller gallery)
#     img_tag = soup.select_one("#imgTagWrapperId img")

#     if not img_tag:
#         return image_urls

#     data = img_tag.get("data-a-dynamic-image")
#     if not data:
#         return image_urls

#     try:
#         images = json.loads(data)
#         for url in images.keys():
#             image_urls.add(url)
#     except Exception:
#         pass

#     return image_urls


# def scrape_amazon(product_name, max_products=10):
#     search_url = f"{BASE_URL}/s?k={quote(product_name)}"
#     response = requests.get(search_url, headers=HEADERS)
#     soup = BeautifulSoup(response.text, "lxml")

#     # ---------- Get valid product links ----------
#     product_links = []

#     for item in soup.select("div[data-asin]"):
#         asin = item.get("data-asin")
#         if not asin:
#             continue

#         a_tag = item.select_one("a.a-link-normal[href]")
#         if not a_tag:
#             continue

#         href = a_tag["href"]
#         if any(x in href for x in ["sspa", "click", "aax"]):
#             continue

#         product_url = href if href.startswith("http") else BASE_URL + href

#         if product_url not in product_links:
#             product_links.append(product_url)

#         if len(product_links) >= max_products:
#             break

#     all_products = []

#     # ---------- Scrape each product ----------
#     for link in product_links:
#         print("Scraping:", link)

#         try:
#             r = requests.get(link, headers=HEADERS, timeout=15)
#             s = BeautifulSoup(r.text, "lxml")

#             # Title
#             title_tag = s.select_one("#productTitle")
#             title = clean_text(title_tag.get_text()) if title_tag else ""

#             # ✅ Seller images ONLY
#             image_urls = extract_seller_images(s)

#             product_data = {
#                 "product_type": product_name,
#                 "product_title": title,
#                 "product_url": link,
#                 "product_images": ", ".join(image_urls),
#                 "image_count": len(image_urls),
#                 "product_dimensions": ""
#             }

#             # ---------- Specifications → SEPARATE COLUMNS ----------
#             for table in s.select("table"):
#                 for row in table.select("tr"):
#                     th = row.select_one("th")
#                     td = row.select_one("td")
#                     if th and td:
#                         key = clean_text(th.get_text())
#                         value = clean_text(td.get_text())

#                         product_data[key] = value

#                         if "dimension" in key.lower():
#                             product_data["product_dimensions"] = value

#             all_products.append(product_data)
#             time.sleep(random.uniform(2, 4))

#         except Exception as e:
#             print("Failed:", link)
#             print(e)

#     # ---------- Save CSV ----------
#     df = pd.DataFrame(all_products)
#     csv_file = "amazon_products.csv"

#     if os.path.exists(csv_file):
#         df.to_csv(csv_file, mode="a", index=False, header=False)
#     else:
#         df.to_csv(csv_file, index=False)

#     print("\nDONE -> amazon_products.csv created (ONLY seller images included)")


# if __name__ == "__main__":
#     product = input("Enter product name: ").strip()
#     if product:
#         scrape_amazon(product,max_products=1)
#     else:
#         print("No product entered.")


import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
from urllib.parse import quote
import os
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9"
}
BASE_URL = "https://www.amazon.in"


def clean_text(text):
    if not text:
        return ""
    return (
        text.replace("\u200e", "")
            .replace("\u200f", "")
            .replace("\xa0", " ")
            .strip()
    )


def extract_seller_images(soup):
    """
    Extract ONLY seller-uploaded product images (No customer review images)
    """
    image_urls = set()
    img_tag = soup.select_one("#imgTagWrapperId img")
    if not img_tag:
        return image_urls

    data = img_tag.get("data-a-dynamic-image")
    if not data:
        return image_urls

    try:
        images = json.loads(data)
        for url in images.keys():
            image_urls.add(url)
    except Exception:
        pass

    return image_urls


def _write_header_only_csv(csv_file="amazon_products.csv"):
    """
    Ensures the CSV always has headers even if no products could be scraped.
    This prevents pandas EmptyDataError downstream.
    """
    headers = ["product_type", "product_title", "product_url", "product_images", "image_count", "product_dimensions"]
    df = pd.DataFrame(columns=headers)

    # Overwrite to keep file valid
    df.to_csv(csv_file, index=False)


def scrape_amazon(product_name, max_products=10):
    search_url = f"{BASE_URL}/s?k={quote(product_name)}"

    # ✅ Add timeout + status check
    response = requests.get(search_url, headers=HEADERS, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    # ---------- Get valid product links ----------
    product_links = []

    for item in soup.select("div[data-asin]"):
        asin = item.get("data-asin")
        if not asin:
            continue

        a_tag = item.select_one("a.a-link-normal[href]")
        if not a_tag:
            continue

        href = a_tag["href"]
        if any(x in href for x in ["sspa", "click", "aax"]):
            continue

        product_url = href if href.startswith("http") else BASE_URL + href

        if product_url not in product_links:
            product_links.append(product_url)

        if len(product_links) >= max_products:
            break

    all_products = []

    # ---------- Scrape each product ----------
    for link in product_links:
        print("Scraping:", link)

        try:
            r = requests.get(link, headers=HEADERS, timeout=15)
            r.raise_for_status()
            s = BeautifulSoup(r.text, "lxml")

            title_tag = s.select_one("#productTitle")
            title = clean_text(title_tag.get_text()) if title_tag else ""

            image_urls = extract_seller_images(s)

            product_data = {
                "product_type": product_name,
                "product_title": title,
                "product_url": link,
                "product_images": ", ".join(image_urls),
                "image_count": len(image_urls),
                "product_dimensions": ""
            }

            # ---------- Specifications → SEPARATE COLUMNS ----------
            for table in s.select("table"):
                for row in table.select("tr"):
                    th = row.select_one("th")
                    td = row.select_one("td")
                    if th and td:
                        key = clean_text(th.get_text())
                        value = clean_text(td.get_text())
                        if key:
                            product_data[key] = value
                            if "dimension" in key.lower():
                                product_data["product_dimensions"] = value

            all_products.append(product_data)
            time.sleep(random.uniform(2, 4))

        except Exception as e:
            print("Failed:", link)
            print(e)

    # ---------- Save CSV ----------
    csv_file = "amazon_products.csv"

    # ✅ Critical fix: never write a headerless/empty CSV
    if not all_products:
        print(f"[WARN] No products scraped for '{product_name}'. Writing header-only CSV (so pipeline won’t crash).")
        if not os.path.exists(csv_file) or os.path.getsize(csv_file) == 0:
            _write_header_only_csv(csv_file)
        return

    df = pd.DataFrame(all_products)

    if os.path.exists(csv_file) and os.path.getsize(csv_file) > 0:
        # append rows only (no header)
        df.to_csv(csv_file, mode="a", index=False, header=False)
    else:
        # write header + rows
        df.to_csv(csv_file, index=False)

    print("\nDONE -> amazon_products.csv created (ONLY seller images included)")


if __name__ == "__main__":
    product = input("Enter product name: ").strip()
    if product:
        scrape_amazon(product, max_products=1)
    else:
        print("No product entered.")