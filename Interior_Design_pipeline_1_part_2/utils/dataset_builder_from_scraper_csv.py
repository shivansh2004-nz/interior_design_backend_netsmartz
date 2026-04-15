# utils/dataset_builder_from_scraper_csv.py
from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd
import requests


def _ensure_dir(p: str | Path) -> None:
    Path(p).mkdir(parents=True, exist_ok=True)


def _first_image_url(product_images_field) -> str | None:
    if product_images_field is None:
        return None
    s = str(product_images_field).strip()
    if not s:
        return None

    parts = [x.strip() for x in s.split(",") if x.strip()]
    for u in parts:
        if u.startswith("http://") or u.startswith("https://"):
            return u
    return None


def _sanitize_folder_name(name: str) -> str:
    name = (name or "").strip().lower()
    if not name:
        return "unknown"
    name = name.replace("/", "_").replace("\\", "_")
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = name.strip("_")
    return name or "unknown"


def _unique_folder_name(base: str, used: dict[str, int]) -> str:
    if base not in used:
        used[base] = 1
        return base
    used[base] += 1
    return f"{base}__{used[base]}"


def _download_image(url: str, out_path: Path, timeout: int = 30) -> None:
    r = requests.get(url, stream=True, timeout=timeout)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 64):
            if chunk:
                f.write(chunk)


def build_dataset_from_amazon_csv(
    csv_path: str = "amazon_products.csv",
    out_dir: str = "Dataset",
    image_filename: str = "image.png",
    overwrite_images: bool = True,
) -> str:
    """
    Builds:
      Dataset/products.csv
      Dataset/<product_type>/image.png
    """
    csv_p = Path(csv_path)

    if not csv_p.exists():
        raise FileNotFoundError(f"CSV not found: {csv_p.resolve()}")

    # ✅ Fix #1: detect empty file early (prevents pandas EmptyDataError)
    if csv_p.stat().st_size == 0:
        raise ValueError(
            f"CSV exists but is EMPTY: {csv_p.resolve()}\n"
            f"This usually means the scraper didn't collect any products.\n"
            f"Common causes: Amazon blocked the request/CAPTCHA, no valid product links, or product pages failed to parse."
        )

    out_dir_p = Path(out_dir)
    _ensure_dir(out_dir_p)

    # ✅ Fix #2: if the file has only blank lines, pandas still errors; handle that too
    try:
        df = pd.read_csv(csv_p)
    except pd.errors.EmptyDataError:
        raise ValueError(
            f"CSV has no readable header/rows: {csv_p.resolve()}\n"
            f"It may contain only blank lines or invalid content."
        )

    required = ["product_type", "product_title", "product_url", "product_images"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"CSV is missing required columns: {missing}\n"
            f"Found columns: {list(df.columns)}"
        )

    # ✅ Fix #3: if df is empty (0 rows), stop with a helpful error
    if df.shape[0] == 0:
        raise ValueError(
            f"CSV loaded but has 0 rows: {csv_p.resolve()}\n"
            f"That means scraping produced no product entries."
        )

    used_names: dict[str, int] = {}
    rows_out = []

    for _, row in df.iterrows():
        product_type_raw = row.get("product_type", "")
        base_folder = _sanitize_folder_name(str(product_type_raw))
        folder_name = _unique_folder_name(base_folder, used_names)

        product_folder = out_dir_p / folder_name
        _ensure_dir(product_folder)

        local_img_path = product_folder / image_filename

        image_url = _first_image_url(row.get("product_images"))
        image_status = "skipped_no_image_url"

        if image_url:
            if local_img_path.exists() and not overwrite_images:
                image_status = "exists_skipped"
            else:
                try:
                    _download_image(image_url, local_img_path)
                    image_status = "downloaded"
                except Exception as e:
                    image_status = f"download_failed:{type(e).__name__}"

        out_row = dict(row)
        out_row.update(
            {
                "dataset_product_folder": folder_name,
                "selected_image_url": image_url or "",
                "local_image": str(local_img_path).replace("\\", "/"),
                "image_status": image_status,
            }
        )
        rows_out.append(out_row)

    out_csv = out_dir_p / "products.csv"
    pd.DataFrame(rows_out).to_csv(out_csv, index=False, encoding="utf-8")
    return str(out_csv)


if __name__ == "__main__":
    out = build_dataset_from_amazon_csv(
        csv_path="amazon_products.csv",
        out_dir="Dataset",
        image_filename="image.png",
        overwrite_images=True,
    )
    print("✅ Wrote:", out)