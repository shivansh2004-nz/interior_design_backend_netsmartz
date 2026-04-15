# # utils/upload_images_to_cloud.py
import os
from pathlib import Path

import pandas as pd
import cloudinary
import cloudinary.uploader

from utils.config import load_settings


def _configure_cloudinary(settings: dict):
    cloud_name = settings.get("CLOUDINARY_CLOUD_NAME", "").strip()
    api_key = settings.get("CLOUDINARY_API_KEY", "").strip()
    api_secret = settings.get("CLOUDINARY_API_SECRET", "").strip()

    missing = []
    if not cloud_name: missing.append("CLOUDINARY_CLOUD_NAME")
    if not api_key: missing.append("CLOUDINARY_API_KEY")
    if not api_secret: missing.append("CLOUDINARY_API_SECRET")

    if missing:
        raise RuntimeError(
            "Cloudinary credentials missing in .env.\n"
            "Set:\n"
            "  CLOUDINARY_CLOUD_NAME\n"
            "  CLOUDINARY_API_KEY\n"
            "  CLOUDINARY_API_SECRET\n"
            f"Missing: {', '.join(missing)}"
        )

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True
    )


def _pick_one_cutout(cutouts_dir: Path):
    if not cutouts_dir.exists() or not cutouts_dir.is_dir():
        return None

    candidates = sorted(cutouts_dir.glob("*_cutout.png"))
    if not candidates:
        return None

    return candidates[0]


def _is_missing_url(v) -> bool:
    """
    Treat NaN / 'nan' / '' as missing.
    This fixes Pipeline-2 CSV where public_cutout_url starts as NaN.
    """
    if v is None:
        return True
    # pandas NaN
    try:
        if pd.isna(v):
            return True
    except Exception:
        pass
    s = str(v).strip()
    return (s == "") or (s.lower() == "nan")


def upload_assets_and_update_products_csv(
    room_image_path: str,
    cloud_prefix: str = "interior_design",
    overwrite: bool = True,
    skip_if_already_present: bool = True,
):
    """
    Uploads:
      1. ONE *_cutout.png per Dataset/<product>/cutouts/
      2. The room image

    Updates Dataset/products.csv:
      - public_cutout_url
      - room_public_url
    """

    settings = load_settings()
    _configure_cloudinary(settings)

    dataset_dir = settings["DATASET_DIR"]
    dataset_path = Path(dataset_dir)

    products_csv = dataset_path / "products.csv"
    if not products_csv.exists():
        raise FileNotFoundError(f"products.csv not found at: {products_csv}")

    df = pd.read_csv(products_csv)

    if "dataset_product_folder" not in df.columns:
        raise RuntimeError("products.csv must contain 'dataset_product_folder' column.")

    if "public_cutout_url" not in df.columns:
        df["public_cutout_url"] = ""

    if "room_public_url" not in df.columns:
        df["room_public_url"] = ""

    # -------------------------
    # 1️⃣ Upload Room Image
    # -------------------------
    room_path = Path(room_image_path)
    if not room_path.exists():
        raise FileNotFoundError(f"Room image not found: {room_image_path}")

    room_public_id = f"{cloud_prefix}/room/{room_path.stem}"

    print(f"[STEP] Uploading room image: {room_path.name}")

    room_res = cloudinary.uploader.upload(
        str(room_path),
        public_id=room_public_id,
        overwrite=overwrite,
        resource_type="image"
    )

    room_url = room_res.get("secure_url", "")
    print(f"[OK] Room uploaded -> {room_url}")

    # -------------------------
    # 2️⃣ Upload Cutouts
    # -------------------------
    cutout_urls = []

    for _, row in df.iterrows():
        folder = str(row.get("dataset_product_folder", "")).strip()

        if not folder:
            cutout_urls.append("")
            continue

        existing_url_raw = row.get("public_cutout_url", "")

        # ✅ FIX: only skip if URL is actually present and valid-ish (not NaN)
        if skip_if_already_present and (not _is_missing_url(existing_url_raw)):
            cutout_urls.append(str(existing_url_raw).strip())
            continue

        cutouts_dir = dataset_path / folder / "cutouts"
        chosen = _pick_one_cutout(cutouts_dir)

        if chosen is None:
            cutout_urls.append("")
            print(f"[WARN] No cutout found for {folder}")
            continue

        public_id = f"{cloud_prefix}/cutouts/{folder}/{chosen.stem}"

        try:
            res = cloudinary.uploader.upload(
                str(chosen),
                public_id=public_id,
                overwrite=overwrite,
                resource_type="image",
                format="png"
            )

            url = res.get("secure_url", "")
            cutout_urls.append(url)

            print(f"[OK] {folder} cutout uploaded -> {url}")

        except Exception as e:
            cutout_urls.append("")
            print(f"[FAIL] {folder}: {e}")

    df["public_cutout_url"] = cutout_urls
    df["room_public_url"] = room_url

    df.to_csv(products_csv, index=False, encoding="utf-8")

    print("\n✅ Upload complete.")
    print(f"✅ Updated: {products_csv}")
    print("Columns updated: public_cutout_url, room_public_url")


if __name__ == "__main__":
    # Example manual run
    upload_assets_and_update_products_csv(room_image_path="room.jpg")