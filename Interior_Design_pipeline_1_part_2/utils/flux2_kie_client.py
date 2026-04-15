# utils/flux2_kie_client.py
import requests
import time
import json
import os
import csv
from utils.config import load_settings

# ==============================
# CONFIGURATION
# ==============================
API_KEY = load_settings()["KIE_API_KEY"]

CREATE_URL = "https://api.kie.ai/api/v1/jobs/createTask"
STATUS_URL = "https://api.kie.ai/api/v1/jobs/recordInfo"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

ASPECT_RATIO = "4:3"
RESOLUTION = "1K"

# Folder to save outputs
OUTPUT_DIR = "generated_images"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ==============================
# CSV -> INPUT_URLS + PROMPT
# ==============================
REQUIRED_COLUMNS = {"product_type", "public_cutout_url", "room_public_url"}


def _is_http_url(s: str) -> bool:
    s = (s or "").strip()
    return s.startswith("http://") or s.startswith("https://")


def build_input_urls_and_prompt_from_csv(csv_path: str):
    """
    Robustly reads YOUR pipeline CSV and constructs:
      - INPUT_URLS: all non-empty public_cutout_url (in CSV order), then room_public_url (once, last)
      - prompt: EXACT same wording pattern as your reference prompt, generalized to N items

    NO assumptions:
      - Uses ONLY columns: product_type, public_cutout_url, room_public_url
      - Validates presence of required columns
      - Validates at least 1 cutout exists
      - Validates room_public_url exists and is consistent across rows (or chooses the single unique one)
    """

    if not os.path.exists(csv_path):
        raise RuntimeError(f"CSV file not found: {csv_path}")

    furniture_types = []
    furniture_urls = []
    room_urls_seen = set()

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        headers = set(reader.fieldnames or [])

        missing = REQUIRED_COLUMNS - headers
        if missing:
            raise RuntimeError(
                f"CSV is missing required columns: {sorted(missing)}. Found columns: {sorted(headers)}"
            )

        for row_idx, row in enumerate(reader, start=2):  # header is line 1
            product_type = (row.get("product_type") or "").strip().lower()
            cutout_url = (row.get("public_cutout_url") or "").strip()
            room_url = (row.get("room_public_url") or "").strip()

            if room_url:
                room_urls_seen.add(room_url)

            # Only include furniture whose cutouts were uploaded (non-empty URL)
            if cutout_url:
                if not product_type:
                    raise RuntimeError(
                        f"Row {row_idx}: public_cutout_url is present but product_type is empty."
                    )
                if not _is_http_url(cutout_url):
                    raise RuntimeError(
                        f"Row {row_idx}: public_cutout_url is not a valid http(s) URL: {cutout_url}"
                    )

                furniture_types.append(product_type)
                furniture_urls.append(cutout_url)

    if not furniture_urls:
        raise RuntimeError(
            "No furniture cutouts found. Every row had empty public_cutout_url."
        )

    # Determine room URL (must exist, ideally consistent)
    room_urls_seen = {u for u in room_urls_seen if u.strip()}

    if not room_urls_seen:
        raise RuntimeError(
            "room_public_url is missing/empty in the CSV (no valid room URL found)."
        )

    if len(room_urls_seen) > 1:
        raise RuntimeError(
            f"Multiple different room_public_url values found in CSV: {sorted(room_urls_seen)}. "
            f"Expected exactly 1."
        )

    room_url = next(iter(room_urls_seen))
    if not _is_http_url(room_url):
        raise RuntimeError(f"room_public_url is not a valid http(s) URL: {room_url}")

    # Build INPUT_URLS in the same order as the CSV cutouts appeared, then room last
    INPUT_URLS = list(furniture_urls) + [room_url]

    # Build prompt with EXACT wording pattern
    # Reference:
    # "Place the bed in image 1 and the chair in image 2 in the room in image 3
    #  and make it look as if the bed and the chair were naturally present in the room."
    #
    # Generalized to N:
    # "Place the bed in image 1 and the wardrobe in image 2 and the nightstand in image 3
    #  in the room in image 4 and make it look as if the bed and the wardrobe and the nightstand
    #  were naturally present in the room."
    #
    # NOTE: No wording changes, only expanding the 'and the ...' chain.

    room_image_index = len(furniture_types) + 1

    place_parts = [f"the {name} in image {i}" for i, name in enumerate(furniture_types, start=1)]
    place_clause = "Place " + " and ".join(place_parts)

    room_clause = f"in the room in image {room_image_index}"

    as_if_parts = [f"the {name}" for name in furniture_types]
    as_if_clause = "and make it look as if " + " and ".join(as_if_parts) + f" were naturally present in the room without changing the viewing angle of the room. Do not change the room in image {room_image_index} at all."

    prompt = f"{place_clause} {room_clause} {as_if_clause}"

    return INPUT_URLS, prompt


# ==============================
# DOWNLOAD IMAGE FUNCTION
# ==============================
def download_image(url, index):
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        filename = os.path.join(OUTPUT_DIR, f"output_{index}.png")
        with open(filename, "wb") as f:
            f.write(response.content)

        print(f"💾 Saved locally → {filename}")

    except Exception as e:
        print(f"⚠️ Failed to download image: {e}")


# ==============================
# STEP 1 — CREATE TASK
# ==============================
def create_task(INPUT_URLS, PROMPT):
    payload = {
        "model": "flux-2/pro-image-to-image",
        "input": {
            "input_urls": INPUT_URLS,
            "prompt": PROMPT,
            "aspect_ratio": ASPECT_RATIO,
            "resolution": RESOLUTION
        }
    }

    response = requests.post(CREATE_URL, headers=HEADERS, json=payload, timeout=30)
    data = response.json()

    if data.get("code") != 200:
        raise Exception(f"Task creation failed: {data}")

    task_id = data["data"]["taskId"]
    print("✅ Task created:", task_id)
    return task_id


# ==============================
# STEP 2 — POLL STATUS
# ==============================
def check_status(task_id):
    params = {"taskId": task_id}
    response = requests.get(STATUS_URL, headers=HEADERS, params=params, timeout=30)
    return response.json()


# ==============================
# MAIN FLOW
# ==============================
def run_generation(csv_path):
    INPUT_URLS, prompt = build_input_urls_and_prompt_from_csv(csv_path)

    # EXACTLY keep your variable names
    PROMPT = prompt

    # Optional: print what will be sent (helps debugging your pipeline)
    print("\n--- INPUT_URLS (in order) ---")
    for i, u in enumerate(INPUT_URLS, start=1):
        print(f"image {i}: {u}")

    print("\n--- PROMPT ---")
    print(PROMPT)
    print("----------------------------\n")

    task_id = create_task(INPUT_URLS, PROMPT)

    print("⏳ Waiting for result...")

    while True:
        result = check_status(task_id)
        state = result["data"]["state"]

        if state == "waiting":
            print("⏱ Still processing...")
            time.sleep(5)

        elif state == "success":
            result_json = json.loads(result["data"]["resultJson"])
            image_urls = result_json["resultUrls"]

            print("\n🎉 Generation complete!")

            for i, url in enumerate(image_urls, start=1):
                print("🌐 Generated Image URL:", url)
                download_image(url, i)

            return image_urls

        elif state == "fail":
            print("❌ Generation failed")
            print("Reason:", result["data"].get("failMsg"))
            return None


# ==============================
# RUN SCRIPT
# ==============================
if __name__ == "__main__":
    run_generation("Dataset/products.csv")