# utils/dataset_builder_from_user_assets.py
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import pandas as pd


def _ensure_dir(p: str | Path) -> None:
    Path(p).mkdir(parents=True, exist_ok=True)


def _sanitize_folder_name(name: str) -> str:
    name = (name or "").strip().lower()
    if not name:
        return "unknown"
    name = name.replace("/", "_").replace("\\", "_")
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = name.strip("_")
    return name or "unknown"


def build_dataset_from_user_assets(
    items: list[tuple[str, str]],
    out_dir: str = "Dataset",
    image_filename: str = "image.png",
    overwrite_images: bool = True,
) -> str:
    """
    items: list of (product_type, image_path)

    Creates:
      Dataset/<product_type>/image.png
      Dataset/products.csv   (with product_type + dataset_product_folder + local_image)
    """
    out_dir_p = Path(out_dir)
    _ensure_dir(out_dir_p)

    used_names: dict[str, int] = {}
    rows_out = []

    for product_type, img_path in items:
        if not product_type or not str(product_type).strip():
            raise ValueError(f"Invalid product_type: {product_type!r}")

        img_p = Path(img_path)
        if not img_p.exists():
            raise FileNotFoundError(f"User asset not found: {img_p.resolve()}")

        base = _sanitize_folder_name(product_type)
        if base not in used_names:
            used_names[base] = 1
            folder_name = base
        else:
            used_names[base] += 1
            folder_name = f"{base}__{used_names[base]}"

        product_folder = out_dir_p / folder_name
        _ensure_dir(product_folder)

        local_img_path = product_folder / image_filename

        if local_img_path.exists() and not overwrite_images:
            status = "exists_skipped"
        else:
            shutil.copyfile(img_p, local_img_path)
            status = "copied"

        rows_out.append(
            {
                "product_type": str(product_type).strip().lower(),
                "dataset_product_folder": folder_name,
                "local_image": str(local_img_path).replace("\\", "/"),
                "image_status": status,
                # keep these columns empty for now; upload step will fill them
                "public_cutout_url": "",
                "room_public_url": "",
            }
        )

    out_csv = out_dir_p / "products.csv"
    pd.DataFrame(rows_out).to_csv(out_csv, index=False, encoding="utf-8")
    return str(out_csv)