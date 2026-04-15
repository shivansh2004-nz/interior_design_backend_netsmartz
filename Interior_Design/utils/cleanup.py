# utils/cleanup.py
import csv
import re
from urllib.parse import urlparse

import cloudinary
import cloudinary.uploader

from utils.config import load_settings


REQUIRED_COLUMNS = {"public_cutout_url", "room_public_url"}


def _cloudinary_public_id_from_url(url: str, expected_cloud_name: str) -> str:
    """
    Convert a Cloudinary delivery URL to a public_id.

    Example URL:
      https://res.cloudinary.com/<cloud>/image/upload/v1234/folder/name.png
    public_id:
      folder/name

    Safety:
      - Ensures URL belongs to expected cloud_name
      - Only supports /image/upload/ delivery URLs
    """
    url = (url or "").strip()
    if not url:
        raise RuntimeError("Empty URL")

    parsed = urlparse(url)
    if not parsed.netloc.endswith("cloudinary.com"):
        raise RuntimeError(f"Not a Cloudinary domain: {url}")

    # Safety: cloud name check
    # Typical host path includes "/<cloud_name>/"
    if f"/{expected_cloud_name}/" not in parsed.path:
        raise RuntimeError(f"URL not from expected cloud '{expected_cloud_name}': {url}")

    # Extract tail after /image/upload/
    # Handles optional version segment like v1234/
    m = re.search(r"/image/upload/(?:v\d+/)?(.+)$", parsed.path)
    if not m:
        raise RuntimeError(f"Could not parse Cloudinary upload path: {url}")

    tail = m.group(1)

    # Remove extension
    tail = re.sub(r"\.(png|jpg|jpeg|webp)$", "", tail, flags=re.IGNORECASE)

    if not tail:
        raise RuntimeError(f"Parsed empty public_id from URL: {url}")

    return tail


def delete_cloudinary_assets_from_products_csv(products_csv_path: str) -> dict:
    """
    Deletes assets referenced by:
      - public_cutout_url (0..N)
      - room_public_url (exactly 1 unique expected)

    Returns a summary dict.
    """
    settings = load_settings()
    cloud_name = (settings.get("CLOUDINARY_CLOUD_NAME") or "").strip()
    api_key = (settings.get("CLOUDINARY_API_KEY") or "").strip()
    api_secret = (settings.get("CLOUDINARY_API_SECRET") or "").strip()

    if not cloud_name or not api_key or not api_secret:
        raise RuntimeError("Cloudinary credentials missing: CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET")

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )

    cutout_urls = []
    room_urls_seen = set()

    with open(products_csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        headers = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - headers
        if missing:
            raise RuntimeError(
                f"products.csv missing required columns: {sorted(missing)}. Found: {sorted(headers)}"
            )

        for row in reader:
            cu = (row.get("public_cutout_url") or "").strip()
            ru = (row.get("room_public_url") or "").strip()
            if cu:
                cutout_urls.append(cu)
            if ru:
                room_urls_seen.add(ru)

    if not room_urls_seen:
        raise RuntimeError("No room_public_url found in products.csv (cannot cleanup room image).")

    if len(room_urls_seen) > 1:
        raise RuntimeError(f"Multiple room_public_url values found: {sorted(room_urls_seen)}")

    room_url = next(iter(room_urls_seen))

    # URL -> public_id (skip invalid safely, but log in summary)
    public_ids = []
    skipped = []
    for u in cutout_urls + [room_url]:
        try:
            public_ids.append(_cloudinary_public_id_from_url(u, cloud_name))
        except Exception as e:
            skipped.append({"url": u, "reason": str(e)})

    results = []
    ok = 0
    not_found = 0
    failed = 0

    for pid in public_ids:
        try:
            resp = cloudinary.uploader.destroy(pid, resource_type="image", invalidate=True)
            r = (resp.get("result") or "").lower()
            results.append({"public_id": pid, "result": r})

            if r == "ok":
                ok += 1
            elif r == "not found":
                not_found += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            results.append({"public_id": pid, "result": "error", "error": str(e)})

    return {
        "cloud_name": cloud_name,
        "attempted": len(public_ids),
        "deleted_ok": ok,
        "not_found": not_found,
        "failed": failed,
        "skipped": skipped,
        "results": results,
    }