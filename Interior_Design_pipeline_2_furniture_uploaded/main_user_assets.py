# main_user_assets.py
"""
Pipeline-2 (User Assets -> Cutouts -> Upload -> Flux2 -> Cleanup)

✅ Cleanup is ON by default, but runs ONLY at the END (after Flux2 finishes and outputs are downloaded).
Disable cleanup with: --no_cleanup_cloudinary
Preview cleanup without deleting with: --cleanup_dry_run

Usage:
  python main_user_assets.py --room_image room.jpg --items bed=bed.png wardrobe=wardrobe.png
  python main_user_assets.py --room_image room.jpg --items bed=bed.png wardrobe=wardrobe.png --no_cleanup_cloudinary
  python main_user_assets.py --room_image room.jpg --items bed=bed.png wardrobe=wardrobe.png --cleanup_dry_run
"""

import argparse
import os
import re
from pathlib import Path

import cv2
import pandas as pd

from utils.config import load_settings
from utils.io_utils import ensure_dir
from utils.cutout_generator_yolo_sam import generate_cutouts
from utils.upload_images_to_cloud import upload_assets_and_update_products_csv
from utils.flux2_kie_client import run_generation as run_flux2_generation

# ✅ Your cleanup implementation lives in utils/cleanup.py
# It deletes assets referenced in Dataset/products.csv (public_cutout_url + room_public_url)
from utils.cleanup import delete_cloudinary_assets_from_products_csv


# -----------------------------
# Helpers
# -----------------------------
def _sanitize_folder_name(name: str) -> str:
    name = (name or "").strip().lower()
    name = name.replace("/", "_").replace("\\", "_")
    name = re.sub(r"[^a-z0-9]+", "_", name).strip("_")
    return name or "unknown"


def _parse_items(items_list):
    """
    Parses ["bed=path", "chair=path"] -> [("bed","path"), ("chair","path")]
    """
    out = []
    for s in items_list:
        if "=" not in s:
            raise ValueError(f"Invalid --items entry: {s!r}. Expected key=path")
        k, p = s.split("=", 1)
        k = k.strip()
        p = p.strip().strip('"').strip("'")
        if not k or not p:
            raise ValueError(f"Invalid --items entry: {s!r}. Expected key=path")
        out.append((k, p))
    return out


def _write_as_png(src_path: Path, dst_png_path: Path) -> None:
    """
    Ensures the Dataset image is always 'image.png' (as your generator expects).
    Converts if needed; preserves alpha if present.
    """
    img = cv2.imread(str(src_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError(f"Failed to read image: {src_path.resolve()}")

    # If grayscale -> convert to BGR
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    ok = cv2.imwrite(str(dst_png_path), img)
    if not ok:
        raise RuntimeError(f"Failed to write PNG: {dst_png_path.resolve()}")


def build_dataset_from_user_assets(items, dataset_dir: str) -> str:
    """
    Creates:
      Dataset/<folder>/image.png
      Dataset/products.csv

    Returns products.csv path.
    """
    dataset_p = Path(dataset_dir)
    ensure_dir(str(dataset_p))

    used: dict[str, int] = {}
    rows = []

    for product_type, src in items:
        src_p = Path(src)
        if not src_p.exists():
            raise FileNotFoundError(f"User asset not found: {src_p.resolve()}")

        base = _sanitize_folder_name(product_type)

        # Handle duplicates safely: chair, chair__2, chair__3 ...
        if base not in used:
            used[base] = 1
            folder_name = base
        else:
            used[base] += 1
            folder_name = f"{base}__{used[base]}"

        folder_p = dataset_p / folder_name
        ensure_dir(str(folder_p))

        dst_img = folder_p / "image.png"
        _write_as_png(src_p, dst_img)

        rows.append(
            {
                "product_type": str(product_type).strip().lower(),
                "dataset_product_folder": folder_name,
                "local_image": str(dst_img).replace("\\", "/"),
                # These get filled by upload step
                "public_cutout_url": "",
                "room_public_url": "",
            }
        )

    products_csv = dataset_p / "products.csv"
    pd.DataFrame(rows).to_csv(products_csv, index=False, encoding="utf-8")
    return str(products_csv)


# -----------------------------
# CLI
# -----------------------------
def parse_args():
    p = argparse.ArgumentParser("Interior Design Pipeline 2 (User Assets)")

    p.add_argument("--room_image", required=True, help="Path to empty room image")
    p.add_argument(
        "--items",
        nargs="+",
        required=True,
        help="Furniture items as key=path pairs. Example: bed=bed.png chair=chair.png",
    )

    # Optional overrides
    p.add_argument("--dataset_dir", default=None, help="Override DATASET_DIR from config.py")
    p.add_argument("--skip_cutouts", action="store_true", help="Skip cutout generation step")
    p.add_argument("--skip_upload", action="store_true", help="Skip Cloudinary upload step")
    p.add_argument("--skip_flux2", action="store_true", help="Skip Flux2 generation step")

    # Upload knobs (passed to your upload module)
    p.add_argument("--cloud_prefix", default="interior_design", help="Cloudinary public_id prefix")
    p.add_argument("--upload_overwrite", action="store_true", help="Overwrite existing Cloudinary assets")
    p.add_argument(
        "--upload_even_if_url_exists",
        action="store_true",
        help="Upload even if products.csv already has public_cutout_url (forces re-upload)",
    )

    # Cutout knobs (passed to your cutout module)
    p.add_argument("--force_cpu", action="store_true", help="Force CPU for SAM (slower but compatible)")
    p.add_argument("--no_rembg_fallback", action="store_true", help="Disable rembg fallback even if installed")
    p.add_argument("--crop_pad", type=int, default=8, help="Tight-crop pad (pixels) around mask")

    # Cleanup knobs (ON by default; can disable)
    p.add_argument(
        "--no_cleanup_cloudinary",
        action="store_true",
        help="Disable Cloudinary cleanup (cleanup is ON by default, runs at the END).",
    )
    p.add_argument("--cleanup_dry_run", action="store_true", help="Print what would be deleted, but do not delete")

    return p.parse_args()


def main():
    args = parse_args()
    settings = load_settings()

    dataset_dir = args.dataset_dir or settings.get("DATASET_DIR", "Dataset")
    ensure_dir(dataset_dir)

    products_csv_path = os.path.join(dataset_dir, "products.csv")

    # -------------------------
    # Step 1/5: Build Dataset/ from user assets
    # -------------------------
    items = _parse_items(args.items)
    print("\n[STEP 1/5] Building Dataset/ structure from user assets...")
    products_csv = build_dataset_from_user_assets(items, dataset_dir=dataset_dir)
    print(f"[DONE] Wrote: {products_csv}")

    # -------------------------
    # Step 2/5: Cutouts (your exact generator)
    # -------------------------
    if args.skip_cutouts:
        print("\n[SKIP] Cutout generation skipped (--skip_cutouts).")
    else:
        print("\n[STEP 2/5] Generating cutouts (YOLO+SAM + rembg fallback)...")
        summary = generate_cutouts(
            dataset_dir=dataset_dir,
            force_cpu=args.force_cpu,
            use_rembg_fallback=(not args.no_rembg_fallback),
            crop_pad=args.crop_pad,
        )
        print(f"[DONE] Cutouts summary: {summary}")

    # -------------------------
    # Step 3/5: Upload room + cutouts
    # -------------------------
    did_upload = False
    if args.skip_upload:
        print("\n[SKIP] Upload skipped (--skip_upload).")
    else:
        print("\n[STEP 3/5] Uploading room + one *_cutout.png per folder to Cloudinary...")
        upload_assets_and_update_products_csv(
            room_image_path=args.room_image,
            cloud_prefix=args.cloud_prefix,
            overwrite=args.upload_overwrite,
            skip_if_already_present=(not args.upload_even_if_url_exists),
        )
        did_upload = True
        print("[DONE] Upload finished. Updated Dataset/products.csv with public URLs.")

    # -------------------------
    # Step 4/5: Flux2 generation
    # -------------------------
    flux_ok = False
    if args.skip_flux2:
        print("\n[SKIP] Flux2 generation skipped (--skip_flux2).")
        flux_ok = True  # treat as ok if user intentionally skipped
    else:
        print("\n[STEP 4/5] Running Flux2 (Kie API) from Dataset/products.csv ...")
        out_urls = run_flux2_generation(products_csv_path)
        if out_urls:
            flux_ok = True
            print("\n[DONE] Flux2 generation complete. Output URLs:")
            for u in out_urls:
                print(u)
            print(f"\n[DONE] Local outputs directory: {os.path.abspath('generated_images')}")
        else:
            print("\n[WARN] Flux2 returned no outputs (or generation failed). Cleanup will be skipped for safety.")

    # -------------------------
    # Step 5/5: Cleanup (LAST)
    # -------------------------
    # Your cleanup.py deletes assets referenced in products.csv
    # It does NOT delete by prefix, so args.cloud_prefix is not used here.
    if did_upload and flux_ok and (not args.no_cleanup_cloudinary):
        if args.cleanup_dry_run:
            print("\n[STEP 5/5] Cleanup DRY-RUN requested, but current cleanup.py deletes immediately.")
            print("[INFO] To support true dry-run, we'd need to add a dry_run flag to cleanup.py.")
            print("[INFO] Skipping cleanup to avoid accidental deletion.")
        else:
            print(f"\n[STEP 5/5] Cleaning Cloudinary assets referenced in: {products_csv_path}")
            summary = delete_cloudinary_assets_from_products_csv(products_csv_path)
            print(
                f"[DONE] Cleanup summary: attempted={summary.get('attempted')}, "
                f"deleted_ok={summary.get('deleted_ok')}, not_found={summary.get('not_found')}, "
                f"failed={summary.get('failed')}"
            )
    else:
        if args.no_cleanup_cloudinary:
            print("\n[INFO] Cleanup disabled (--no_cleanup_cloudinary).")
        elif not did_upload:
            print("\n[INFO] Cleanup skipped (upload did not run).")
        elif not flux_ok:
            print("\n[INFO] Cleanup skipped (Flux2 did not complete successfully).")


if __name__ == "__main__":
    main()