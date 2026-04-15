import argparse
import os

from utils.config import load_settings
from utils.io_utils import ensure_dir
from utils.amazon_scraper_playwright import scrape_amazon_browser
from utils.dataset_builder_from_scraper_csv import build_dataset_from_amazon_csv
from utils.cutout_generator_yolo_sam import generate_cutouts
from utils.upload_images_to_cloud import upload_assets_and_update_products_csv

# ✅ Flux2 (Kie) integration
from utils.flux2_kie_client import run_generation as run_flux2_generation

# ✅ Cloudinary cleanup integration
from utils.cleanup import delete_cloudinary_assets_from_products_csv


def parse_args():
    p = argparse.ArgumentParser("Interior Design Pipeline 1.2 (User Furnitures -> Scrape -> Dataset -> Cutouts -> Upload -> Flux2 -> Cleanup)")

    p.add_argument("--pipeline_version", default="1.2", help="Pipeline version (should be 1.2 for this script)")
    p.add_argument("--room_image", required=True, help="Path to room image (stored for later modules)")
    p.add_argument("--room_type", required=True)
    p.add_argument("--dimensions", required=True)
    p.add_argument("--style", default="minimal")
    p.add_argument("--budget", default="medium")

    # ✅ User-provided furniture list
    p.add_argument(
        "--user_furnitures",
        required=True,
        help='Comma-separated furniture list, e.g. "bed, chair, wardrobe, side table"',
    )

    # Cutouts (YOLO + SAM)
    p.add_argument("--skip_cutouts", action="store_true", help="Skip YOLO+SAM cutout generation step")
    p.add_argument(
        "--sam_checkpoint",
        default=os.path.join("models", "sam_vit_h_4b8939.pth"),
        help="Path to SAM checkpoint (.pth)",
    )
    p.add_argument("--force_cpu", action="store_true", help="Force CPU for cutout generation")

    # Upload to Cloudinary (only *_cutout.png, one per folder)
    p.add_argument("--skip_upload", action="store_true", help="Skip Cloudinary upload step")
    p.add_argument(
        "--cloud_prefix",
        default="interior_design/cutouts",
        help="Cloudinary public_id prefix (folder path in Cloudinary)",
    )
    p.add_argument(
        "--upload_overwrite",
        action="store_true",
        help="Overwrite existing files on Cloudinary (same public_id)",
    )
    p.add_argument(
        "--upload_even_if_url_exists",
        action="store_true",
        help="Upload even if products.csv already has public_cutout_url",
    )

    # ✅ Flux2 generation
    p.add_argument("--skip_flux2", action="store_true", help="Skip Flux2 (Kie API) generation step")

    # ✅ Cleanup
    p.add_argument("--skip_cleanup", action="store_true", help="Skip Cloudinary cleanup (delete room + cutouts) step")

    return p.parse_args()


def save_user_furniture_list(user_furnitures: str, out_txt_path: str):
    """
    Save comma-separated furniture input into Furnitures.txt
    in one-item-per-line format.
    """
    if not user_furnitures or not user_furnitures.strip():
        return []

    furnitures = []
    for item in user_furnitures.split(","):
        clean_item = item.strip().lower()
        if clean_item and clean_item not in furnitures:
            furnitures.append(clean_item)

    os.makedirs(os.path.dirname(out_txt_path), exist_ok=True)

    with open(out_txt_path, "w", encoding="utf-8") as f:
        for item in furnitures:
            f.write(item + "\n")

    print(f"[DONE] Saved user furniture list to: {out_txt_path}")
    print(f"[DONE] Furniture items: {furnitures}")

    return furnitures


def main():
    args = parse_args()

    if args.pipeline_version != "1.2":
        print(f"[WARN] This script is intended for pipeline 1.2, but got --pipeline_version {args.pipeline_version}")

    settings = load_settings()

    dataset_dir = settings["DATASET_DIR"]
    ensure_dir(dataset_dir)

    # -------------------------
    # Step 1: Furniture list from user input
    # -------------------------
    furn_txt = os.path.join(dataset_dir, "Furnitures.txt")

    furnitures = save_user_furniture_list(
        user_furnitures=args.user_furnitures,
        out_txt_path=furn_txt,
    )

    if not furnitures:
        print("[ERROR] Furniture list empty. Exiting.")
        return

    # -------------------------
    # Step 2: Amazon scraping
    # -------------------------
    utils_dir = os.path.join(os.getcwd(), "utils")
    csv_file = os.path.join(utils_dir, "amazon_products.csv")

    if os.path.exists(csv_file):
        os.remove(csv_file)
        print(f"[OK] Removed old {csv_file}")

    with open(furn_txt, "r", encoding="utf-8") as f:
        items = [line.strip() for line in f if line.strip()]

    for item in items:
        print(f"\n[SCRAPE - CHROME] Item: {item}")
        try:
            scrape_amazon_browser(product_name=item, max_products=1)
        except Exception as e:
            print(f"[WARN] Browser scrape failed for '{item}': {e}")

    if not os.path.exists(csv_file) or os.path.getsize(csv_file) == 0:
        print("[ERROR] amazon_products.csv not created or is empty. Exiting.")
        print(f"[DEBUG] Expected at: {csv_file}")
        return

    # -------------------------
    # Step 3: Build Dataset + download images
    # -------------------------
    out_csv = build_dataset_from_amazon_csv(
        csv_path=csv_file,
        out_dir=dataset_dir,
        image_filename="image.png",
        overwrite_images=True,
    )

    print(f"\n[DONE] Dataset created at: {dataset_dir}")
    print(f"[DONE] Final products.csv: {out_csv}")

    # -------------------------
    # Step 4: Generate cutouts (YOLO + SAM)
    # -------------------------
    if args.skip_cutouts:
        print("\n[SKIP] Cutout generation skipped (--skip_cutouts).")
    else:
        print("\n[STEP] Generating cutouts with YOLO+SAM...")
        try:
            summary = generate_cutouts(
                dataset_dir=dataset_dir,
                sam_checkpoint=args.sam_checkpoint,
                force_cpu=args.force_cpu,
            )
            print(
                f"\n[DONE] Cutouts summary: processed_folders={summary['processed_folders']}, "
                f"skipped_folders={summary['skipped_folders']}, total_cutouts={summary['total_cutouts']}"
            )
        except FileNotFoundError as e:
            print("\n[WARN] Cutout generation could not run (missing SAM checkpoint).")
            print(str(e))
            print("➡️ Put the SAM checkpoint in models/ or pass --sam_checkpoint <path>.")
            return

    # -------------------------
    # Step 5: Upload one *_cutout.png per folder to Cloudinary
    # -------------------------
    if args.skip_upload:
        print("\n[SKIP] Upload skipped (--skip_upload).")
        return

    print("\n[STEP] Uploading transparent cutouts (*_cutout.png) to Cloudinary...")
    try:
        upload_assets_and_update_products_csv(
            room_image_path=args.room_image,
            cloud_prefix=args.cloud_prefix,
            overwrite=args.upload_overwrite,
            skip_if_already_present=not args.upload_even_if_url_exists,
        )
        print("\n[DONE] Upload finished. Check Dataset/products.csv -> public_cutout_url")
    except Exception as e:
        print("\n[ERROR] Upload failed:")
        print(e)
        return

    # -------------------------
    # Step 6: Flux2 (Kie API) generation using Dataset/products.csv
    # -------------------------
    if args.skip_flux2:
        print("\n[SKIP] Flux2 generation skipped (--skip_flux2).")
        return

    products_csv = os.path.join(dataset_dir, "products.csv")
    if not os.path.exists(products_csv):
        print("\n[ERROR] Dataset/products.csv not found after upload step.")
        print(f"[DEBUG] Expected at: {products_csv}")
        return

    print("\n[STEP] Running Flux2 (Kie API) using Dataset/products.csv ...")
    try:
        generated_urls = run_flux2_generation(products_csv)

        if generated_urls:
            print("\n[DONE] Flux2 generation finished. Generated image URLs:")
            for u in generated_urls:
                print(u)
            print(f"\n[DONE] Output images saved in: {os.path.abspath('generated_images')}")

            # -------------------------
            # Step 7: Cleanup Cloudinary (delete room + furniture cutouts)
            # -------------------------
            if args.skip_cleanup:
                print("\n[SKIP] Cleanup skipped (--skip_cleanup).")
                return

            print("\n[STEP] Cleaning up Cloudinary assets (room + cutouts referenced in products.csv)...")
            try:
                summary = delete_cloudinary_assets_from_products_csv(products_csv)
                print(
                    f"[DONE] Cleanup summary: attempted={summary['attempted']}, "
                    f"deleted_ok={summary['deleted_ok']}, not_found={summary['not_found']}, failed={summary['failed']}"
                )
                if summary.get("skipped"):
                    print(f"[WARN] Skipped {len(summary['skipped'])} URL(s) (not deletable / not our cloud).")
            except Exception as e:
                print("\n[WARN] Cleanup failed:")
                print(e)

        else:
            print("\n[ERROR] Flux2 returned no outputs or generation failed.")
    except Exception as e:
        print("\n[ERROR] Flux2 step failed:")
        print(e)


if __name__ == "__main__":
    main()