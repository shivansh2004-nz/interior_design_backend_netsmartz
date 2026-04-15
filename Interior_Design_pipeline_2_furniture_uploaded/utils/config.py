# config.py
import os
from dotenv import load_dotenv

def load_settings():
    load_dotenv()

    cohere_key = (os.getenv("COHERE_API_KEY") or "").strip()
    dataset_dir = (os.getenv("DATASET_DIR") or "Dataset").strip()

    # Cloudinary (optional for other modules; required for upload script)
    cloudinary_cloud_name = (os.getenv("CLOUDINARY_CLOUD_NAME") or "").strip()
    cloudinary_api_key = (os.getenv("CLOUDINARY_API_KEY") or "").strip()
    cloudinary_api_secret = (os.getenv("CLOUDINARY_API_SECRET") or "").strip()

    # Kie.ai (Flux.2 API)
    kie_api_key = (os.getenv("KIE_API_KEY") or "").strip()

    if not cohere_key:
        raise RuntimeError("COHERE_API_KEY missing in .env")

    if not kie_api_key:
        raise RuntimeError("KIE_API_KEY missing in .env")

    return {
        "COHERE_API_KEY": cohere_key,
        "DATASET_DIR": dataset_dir,

        # added
        "CLOUDINARY_CLOUD_NAME": cloudinary_cloud_name,
        "CLOUDINARY_API_KEY": cloudinary_api_key,
        "CLOUDINARY_API_SECRET": cloudinary_api_secret,

        # added
        "KIE_API_KEY": kie_api_key,
    }