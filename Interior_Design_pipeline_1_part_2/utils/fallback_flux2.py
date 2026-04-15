# utils/flux2_kie_client.py
import requests
import time
import json
import os
from config import load_settings

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

# Reference images
INPUT_URLS = [
    "https://res.cloudinary.com/dr0may9zw/image/upload/v1772169919/interior_design/cutouts/cutouts/bed/image_bed_01_cutout.png",   # Bed image
    "https://res.cloudinary.com/dr0may9zw/image/upload/v1772169921/interior_design/cutouts/cutouts/chair/image_chair_01_cutout.png",  # Chair image
    "https://res.cloudinary.com/dr0may9zw/image/upload/v1772169918/interior_design/cutouts/room/room.jpg"  # Empty room image
]


prompt = "Place the bed in image 1 and the chair in image 2 in the room in image 3 and make it look as if the bed and the chair were naturally present in the room."

PROMPT = prompt
ASPECT_RATIO = "4:3"
RESOLUTION = "1K"

# Folder to save outputs
OUTPUT_DIR = "generated_images"
os.makedirs(OUTPUT_DIR, exist_ok=True)


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
def create_task():
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
def run_generation():
    task_id = create_task()

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
    run_generation()