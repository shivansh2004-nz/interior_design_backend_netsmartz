# import os
# import time
# import random
# import io
# from typing import Dict, Set

# import cv2
# import numpy as np
# import torch
# from ultralytics import YOLO

# from segment_anything import sam_model_registry, SamPredictor

# # ---------- Optional fallback background removal (rembg) ----------
# try:
#     from rembg import remove as rembg_remove
#     from PIL import Image
#     REMBG_AVAILABLE = True
# except Exception:
#     REMBG_AVAILABLE = False

# # ---------- Defaults (can be overridden from main.py) ----------
# DATASET_DIR_DEFAULT = "Dataset"
# SAM_TYPE_DEFAULT = "vit_h"
# SAM_CHECKPOINT_DEFAULT = os.path.join("models", "sam_vit_h_4b8939.pth")

# YOLO_WEIGHTS_LOCAL_DEFAULT = os.path.join("models", "yolov8x.pt")
# YOLO_WEIGHTS_FALLBACK_DEFAULT = "yolov8x.pt"  # triggers Ultralytics download/cache

# # ---------- Mapping: folder name -> COCO class ----------
# # COCO classes that matter for your pipeline
# FURNITURE_TO_COCO = {
#     "bed": "bed",
#     "chair": "chair",
#     "couch": "couch",
#     "sofa": "couch",
#     "dining_table": "dining table",
#     "table": "dining table",
#     "tv": "tv",
#     "pottedplant": "potted plant",
#     # Add more if/when needed (must be a COCO class name YOLO knows)
# }


# def ensure_file_exists(path: str, msg: str):
#     if not os.path.exists(path):
#         raise FileNotFoundError(f"{msg}\nMissing: {path}")


# def clean_name(s: str) -> str:
#     s = s.strip().lower().replace(" ", "_")
#     s = "".join(ch for ch in s if ch.isalnum() or ch in ("_", "-", "."))
#     return s


# def normalize_item(item: str) -> str:
#     return clean_name(item)


# def to_rgba_cutout(bgr_img: np.ndarray, mask: np.ndarray) -> np.ndarray:
#     """
#     bgr_img: HxWx3
#     mask: HxW (0/255)
#     returns BGRA cutout with alpha = mask
#     """
#     b, g, r = cv2.split(bgr_img)
#     a = mask.astype(np.uint8)
#     return cv2.merge([b, g, r, a])


# def to_white_bg(bgr_img: np.ndarray, mask: np.ndarray) -> np.ndarray:
#     """
#     white background where mask is 0
#     """
#     white = np.full_like(bgr_img, 255)
#     mask_3 = cv2.merge([mask, mask, mask])
#     out = np.where(mask_3 > 0, bgr_img, white)
#     return out.astype(np.uint8)


# def tight_crop_by_mask(img: np.ndarray, mask: np.ndarray, pad: int = 8):
#     ys, xs = np.where(mask > 0)
#     if len(xs) == 0 or len(ys) == 0:
#         return img, mask

#     x0, x1 = xs.min(), xs.max()
#     y0, y1 = ys.min(), ys.max()

#     x0 = max(0, x0 - pad)
#     y0 = max(0, y0 - pad)
#     x1 = min(img.shape[1] - 1, x1 + pad)
#     y1 = min(img.shape[0] - 1, y1 + pad)

#     crop_img = img[y0 : y1 + 1, x0 : x1 + 1]
#     crop_mask = mask[y0 : y1 + 1, x0 : x1 + 1]
#     return crop_img, crop_mask


# def run_yolo_multi(yolo: YOLO, rgb: np.ndarray, allowed_coco: Set[str]):
#     """
#     Runs YOLO on the image and returns a list of boxes for ONLY allowed COCO classes.
#     boxes are xyxy float pixels.
#     """
#     res = yolo.predict(source=rgb, verbose=False)
#     if not res:
#         return []

#     r0 = res[0]
#     if r0.boxes is None or len(r0.boxes) == 0:
#         return []

#     boxes = []
#     names = r0.names  # id -> class name
#     for b in r0.boxes:
#         cls_id = int(b.cls.item())
#         cls_name = names.get(cls_id, "")
#         if cls_name in allowed_coco:
#             xyxy = b.xyxy[0].detach().cpu().numpy().tolist()
#             boxes.append((cls_name, xyxy))
#     return boxes


# def segment_with_sam(predictor: SamPredictor, rgb: np.ndarray, box_xyxy):
#     """
#     box_xyxy: [x1,y1,x2,y2] in pixel coords
#     returns binary mask (0/255)
#     """
#     predictor.set_image(rgb)
#     box = np.array(box_xyxy, dtype=np.float32)
#     masks, scores, _ = predictor.predict(box=box[None, :], multimask_output=True)
#     if masks is None or len(masks) == 0:
#         return None

#     best_i = int(np.argmax(scores))
#     return masks[best_i].astype(np.uint8) * 255


# def rembg_fallback_cutout(
#     image_path: str,
#     out_dir: str,
#     base: str,
#     crop_pad: int = 8,
#     alpha_thresh: int = 10,
# ) -> int:
#     """
#     Fallback: uses rembg to remove background.
#     Saves BOTH:
#       - <base>_fallback_white.png
#       - <base>_fallback_cutout.png   <-- IMPORTANT: ends with _cutout.png for Cloudinary upload
#     Returns 1 if saved, else 0.
#     """
#     if not REMBG_AVAILABLE:
#         print("[WARN] rembg fallback requested but rembg/Pillow not installed.")
#         return 0

#     # Read & remove BG via rembg
#     try:
#         with Image.open(image_path) as im:
#             im = im.convert("RGBA")
#             out = rembg_remove(im)

#             # rembg sometimes returns bytes depending on version/config
#             if isinstance(out, (bytes, bytearray)):
#                 out = Image.open(io.BytesIO(out)).convert("RGBA")
#             elif isinstance(out, Image.Image):
#                 out = out.convert("RGBA")
#             else:
#                 # attempt to coerce
#                 out = Image.open(io.BytesIO(out)).convert("RGBA")
#     except Exception as e:
#         print(f"[WARN] rembg failed on {image_path}: {e}")
#         return 0

#     rgba = np.array(out)  # HxWx4 (RGBA)
#     if rgba.ndim != 3 or rgba.shape[2] != 4:
#         print(f"[WARN] rembg output unexpected shape: {getattr(rgba, 'shape', None)}")
#         return 0

#     alpha = rgba[:, :, 3]
#     mask = (alpha > alpha_thresh).astype(np.uint8) * 255

#     # sanity: avoid saving empty masks
#     if np.count_nonzero(mask) < 50:
#         print("[WARN] rembg produced near-empty alpha; skipping fallback save.")
#         return 0

#     # Convert RGB->BGR for consistency with your pipeline
#     bgr = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2BGR)

#     # Tight crop like SAM path
#     crop_bgr, crop_mask = tight_crop_by_mask(bgr, mask, pad=crop_pad)

#     white_bgr = to_white_bg(crop_bgr, crop_mask)
#     cutout_bgra = to_rgba_cutout(crop_bgr, crop_mask)

#     # NOTE: cutout MUST end with *_cutout.png as you requested
#     white_path = os.path.join(out_dir, f"{base}_fallback_white.png")
#     cutout_path = os.path.join(out_dir, f"{base}_fallback_cutout.png")

#     cv2.imwrite(white_path, white_bgr)
#     cv2.imwrite(cutout_path, cutout_bgra)

#     print(f"[OK] Fallback saved: {white_path}")
#     print(f"[OK] Fallback saved: {cutout_path}")
#     return 1


# def process_one_image(
#     image_path: str,
#     out_dir: str,
#     yolo: YOLO,
#     predictor: SamPredictor,
#     allowed_coco: Set[str],
#     crop_pad: int = 8,
# ) -> int:
#     """
#     Returns number of objects saved (YOLO+SAM path).
#     """
#     bgr = cv2.imread(image_path, cv2.IMREAD_COLOR)
#     if bgr is None:
#         print(f"[WARN] Could not read image: {image_path}")
#         return 0

#     rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

#     dets = run_yolo_multi(yolo=yolo, rgb=rgb, allowed_coco=allowed_coco)
#     if not dets:
#         return 0

#     saved = 0
#     base = os.path.splitext(os.path.basename(image_path))[0]

#     for idx, (cls_name, xyxy) in enumerate(dets, start=1):
#         mask = segment_with_sam(predictor=predictor, rgb=rgb, box_xyxy=xyxy)
#         if mask is None:
#             continue

#         crop_bgr, crop_mask = tight_crop_by_mask(bgr, mask, pad=crop_pad)

#         white_bgr = to_white_bg(crop_bgr, crop_mask)
#         cutout_bgra = to_rgba_cutout(crop_bgr, crop_mask)

#         # These already end in *_cutout.png for Cloudinary
#         white_path = os.path.join(out_dir, f"{base}_{cls_name}_{idx:02d}_white.png")
#         cutout_path = os.path.join(out_dir, f"{base}_{cls_name}_{idx:02d}_cutout.png")

#         cv2.imwrite(white_path, white_bgr)
#         cv2.imwrite(cutout_path, cutout_bgra)

#         saved += 1
#         print(f"[OK] Saved obj#{idx}: {white_path}")
#         print(f"[OK] Saved obj#{idx}: {cutout_path}")

#         time.sleep(random.uniform(0.05, 0.15))

#     return saved


# def load_yolo_with_fallback(yolo_weights_local: str, yolo_weights_fallback: str) -> YOLO:
#     """
#     Try local weights first. If they exist but are invalid/corrupt, rename them and fall back.
#     If local weights don't exist, fall back and let Ultralytics auto-download/cache.
#     """
#     if os.path.exists(yolo_weights_local):
#         try:
#             print(f"[INFO] Trying local YOLO weights: {yolo_weights_local}")
#             return YOLO(yolo_weights_local)
#         except Exception as e:
#             print(f"[WARN] Local YOLO weights failed to load: {e}")
#             try:
#                 bad_path = yolo_weights_local + ".bad"
#                 os.replace(yolo_weights_local, bad_path)
#                 print(f"[WARN] Renamed invalid weights to: {bad_path}")
#             except Exception:
#                 pass

#     print(f"[INFO] Falling back to '{yolo_weights_fallback}' (Ultralytics will auto-download if needed)")
#     return YOLO(yolo_weights_fallback)


# def generate_cutouts(
#     dataset_dir: str = DATASET_DIR_DEFAULT,
#     sam_checkpoint: str = SAM_CHECKPOINT_DEFAULT,
#     sam_type: str = SAM_TYPE_DEFAULT,
#     yolo_weights_local: str = YOLO_WEIGHTS_LOCAL_DEFAULT,
#     yolo_weights_fallback: str = YOLO_WEIGHTS_FALLBACK_DEFAULT,
#     force_cpu: bool = False,
#     use_rembg_fallback: bool = True,
#     crop_pad: int = 8,
# ) -> Dict[str, int]:
#     """
#     Main callable entrypoint (importable).
#     Returns a summary dict:
#       { "processed_folders": X, "skipped_folders": Y, "total_cutouts": Z, "fallback_cutouts": F }

#     Behavior:
#       - If folder item not in COCO mapping -> (optional) rembg fallback
#       - If YOLO+SAM finds 0 detections -> (optional) rembg fallback
#     """
#     ensure_file_exists(sam_checkpoint, "SAM checkpoint not found. Put it in models/ as planned.")

#     device = "cpu" if force_cpu else ("cuda" if torch.cuda.is_available() else "cpu")
#     print(f"[INFO] Cutouts: Device = {device}")

#     if use_rembg_fallback and not REMBG_AVAILABLE:
#         print("[WARN] use_rembg_fallback=True but rembg not available. Install: pip install rembg pillow")

#     # Load YOLO once
#     yolo = load_yolo_with_fallback(yolo_weights_local, yolo_weights_fallback)

#     # Load SAM once
#     sam = sam_model_registry[sam_type](checkpoint=sam_checkpoint)
#     sam.to(device=device)
#     predictor = SamPredictor(sam)

#     processed = 0
#     skipped = 0
#     total_saved = 0
#     fallback_saved = 0

#     if not os.path.exists(dataset_dir):
#         raise FileNotFoundError(f"Dataset dir not found: {dataset_dir}")

#     # For each folder Dataset/<item>/image.png
#     for folder in os.listdir(dataset_dir):
#         p = os.path.join(dataset_dir, folder)
#         if not os.path.isdir(p):
#             continue

#         img_path = os.path.join(p, "image.png")
#         if not os.path.exists(img_path):
#             continue

#         out_dir = os.path.join(p, "cutouts")
#         os.makedirs(out_dir, exist_ok=True)

#         item_key = normalize_item(folder)
#         coco_class = FURNITURE_TO_COCO.get(item_key)

#         processed += 1
#         base = os.path.splitext(os.path.basename(img_path))[0]

#         # ---- Case A: Not in COCO mapping -> fallback (instead of skip) ----
#         if coco_class is None:
#             if use_rembg_fallback:
#                 print(f"\n[FALLBACK] {folder} not in COCO mapping -> rembg -> {out_dir}")
#                 n_fb = rembg_fallback_cutout(img_path, out_dir, base=base, crop_pad=crop_pad)
#                 total_saved += n_fb
#                 fallback_saved += n_fb
#                 if n_fb == 0:
#                     print(f"[WARN] Fallback produced no cutout for '{folder}'")
#                     skipped += 1
#             else:
#                 print(f"\n[SKIP] '{folder}' not supported by COCO mapping and fallback disabled.")
#                 skipped += 1
#             continue

#         # ---- Case B: In COCO mapping -> YOLO+SAM ----
#         allowed_for_this = {coco_class}
#         print(f"\n[PROCESS] {folder} (COCO class = {coco_class}) -> {out_dir}")

#         n = process_one_image(
#             image_path=img_path,
#             out_dir=out_dir,
#             yolo=yolo,
#             predictor=predictor,
#             allowed_coco=allowed_for_this,
#             crop_pad=crop_pad,
#         )

#         total_saved += n

#         # If YOLO found nothing, try fallback
#         if n == 0:
#             print(f"[WARN] No '{coco_class}' detected for '{folder}'")
#             if use_rembg_fallback:
#                 print(f"[FALLBACK] Trying rembg for '{folder}' -> {out_dir}")
#                 n_fb = rembg_fallback_cutout(img_path, out_dir, base=base, crop_pad=crop_pad)
#                 total_saved += n_fb
#                 fallback_saved += n_fb
#                 if n_fb == 0:
#                     print(f"[WARN] Fallback produced no cutout for '{folder}'")
#                     skipped += 1
#             else:
#                 skipped += 1

#     return {
#         "processed_folders": processed,
#         "skipped_folders": skipped,
#         "total_cutouts": total_saved,
#         "fallback_cutouts": fallback_saved,
#     }


# # Backwards compatible name (if you were using run_on_dataset before)
# def run_on_dataset(dataset_dir: str = DATASET_DIR_DEFAULT):
#     return generate_cutouts(dataset_dir=dataset_dir)


# if __name__ == "__main__":
#     generate_cutouts()

import io
import inspect
import os
import random
import time
from typing import Dict, List, Optional, Set, Tuple

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from segment_anything import SamPredictor, sam_model_registry

# ---------- Optional fallback background removal (rembg) ----------
try:
    from rembg import remove as rembg_remove
    from PIL import Image
    REMBG_AVAILABLE = True
except Exception:
    REMBG_AVAILABLE = False
    Image = None
    rembg_remove = None

# ---------- Optional Grounding DINO fallback ----------
try:
    from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
    GROUNDING_DINO_AVAILABLE = True
except Exception:
    GROUNDING_DINO_AVAILABLE = False
    AutoModelForZeroShotObjectDetection = None
    AutoProcessor = None

# ---------- Defaults (can be overridden from main.py) ----------
DATASET_DIR_DEFAULT = "Dataset"
SAM_TYPE_DEFAULT = "vit_h"
SAM_CHECKPOINT_DEFAULT = os.path.join("models", "sam_vit_h_4b8939.pth")

YOLO_WEIGHTS_LOCAL_DEFAULT = os.path.join("models", "yolov8x.pt")
YOLO_WEIGHTS_FALLBACK_DEFAULT = "yolov8x.pt"  # triggers Ultralytics download/cache only if local missing

GROUNDING_DINO_MODEL_ID_DEFAULT = "IDEA-Research/grounding-dino-base"
GROUNDING_DINO_BOX_THRESHOLD_DEFAULT = 0.30
GROUNDING_DINO_TEXT_THRESHOLD_DEFAULT = 0.20

# ---------- Mapping: folder name -> COCO class ----------
FURNITURE_TO_COCO = {
    "bed": "bed",
    "chair": "chair",
    "couch": "couch",
    "sofa": "couch",
    "dining_table": "dining table",
    "table": "dining table",
    "tv": "tv",
    "pottedplant": "potted plant",
}

# ---------- Prompt aliases for Grounding DINO ----------
GROUNDING_PROMPT_MAP = {
    "bed": "bed",
    "chair": "chair",
    "couch": "couch",
    "sofa": "sofa",
    "dining_table": "dining table",
    "table": "table",
    "coffee_table": "coffee table",
    "console_table": "console table",
    "desk": "desk",
    "dressing_table": "dressing table",
    "nightstand": "nightstand",
    "side_table": "side table",
    "wardrobe": "wardrobe",
    "cabinet": "cabinet",
    "bookshelf": "bookshelf",
    "drawer": "drawer chest",
}

_yolo_model_cache: Dict[str, YOLO] = {}
_grounding_processor_cache = None
_grounding_model_cache = None
_grounding_model_cache_key: Optional[Tuple[str, str]] = None


def ensure_file_exists(path: str, msg: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"{msg}\nMissing: {path}")


def clean_name(s: str) -> str:
    s = s.strip().lower().replace(" ", "_")
    s = "".join(ch for ch in s if ch.isalnum() or ch in ("_", "-", "."))
    return s


def normalize_item(item: str) -> str:
    return clean_name(item)


def get_grounding_prompt(item_key: str) -> str:
    return GROUNDING_PROMPT_MAP.get(item_key, item_key.replace("_", " "))


def to_rgba_cutout(bgr_img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    b, g, r = cv2.split(bgr_img)
    a = mask.astype(np.uint8)
    return cv2.merge([b, g, r, a])


def to_white_bg(bgr_img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    white = np.full_like(bgr_img, 255)
    mask_3 = cv2.merge([mask, mask, mask])
    out = np.where(mask_3 > 0, bgr_img, white)
    return out.astype(np.uint8)


def tight_crop_by_mask(img: np.ndarray, mask: np.ndarray, pad: int = 8):
    ys, xs = np.where(mask > 0)
    if len(xs) == 0 or len(ys) == 0:
        return img, mask

    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()

    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(img.shape[1] - 1, x1 + pad)
    y1 = min(img.shape[0] - 1, y1 + pad)

    crop_img = img[y0 : y1 + 1, x0 : x1 + 1]
    crop_mask = mask[y0 : y1 + 1, x0 : x1 + 1]
    return crop_img, crop_mask


def run_yolo_multi(yolo: YOLO, rgb: np.ndarray, allowed_coco: Set[str]):
    res = yolo.predict(source=rgb, verbose=False)
    if not res:
        return []

    r0 = res[0]
    if r0.boxes is None or len(r0.boxes) == 0:
        return []

    boxes = []
    names = r0.names
    for b in r0.boxes:
        cls_id = int(b.cls.item())
        cls_name = names.get(cls_id, "")
        if cls_name in allowed_coco:
            conf = float(b.conf.item()) if hasattr(b, "conf") else 0.0
            xyxy = b.xyxy[0].detach().cpu().numpy().tolist()
            boxes.append((cls_name, xyxy, conf))
    return boxes


def segment_with_sam(predictor: SamPredictor, rgb: np.ndarray, box_xyxy):
    predictor.set_image(rgb)
    box = np.array(box_xyxy, dtype=np.float32)
    masks, scores, _ = predictor.predict(box=box[None, :], multimask_output=True)
    if masks is None or len(masks) == 0:
        return None

    best_i = int(np.argmax(scores))
    return masks[best_i].astype(np.uint8) * 255


def _box_area(xyxy: List[float]) -> float:
    x1, y1, x2, y2 = xyxy
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def choose_best_detection(dets: List[Tuple[str, List[float], float]]):
    if not dets:
        return None
    return max(dets, key=lambda x: (x[2], _box_area(x[1])))


def load_yolo_with_fallback(yolo_weights_local: str, yolo_weights_fallback: str) -> YOLO:
    """
    Explicit local-first behavior:
      1) if models/yolov8x.pt exists -> use it
      2) else fall back to 'yolov8x.pt' so Ultralytics can auto-download/cache
    If a local file exists but is corrupt, it is renamed to .bad and fallback is used.
    """
    cache_key = f"{yolo_weights_local}||{yolo_weights_fallback}"
    if cache_key in _yolo_model_cache:
        return _yolo_model_cache[cache_key]

    weights_path = yolo_weights_local
    if os.path.exists(yolo_weights_local):
        print(f"[INFO] Using local YOLO weights: {yolo_weights_local}")
    else:
        print(f"[WARN] Local YOLO weights not found at: {yolo_weights_local}")
        print(f"[INFO] Falling back to '{yolo_weights_fallback}' (Ultralytics may auto-download/cache it)")
        weights_path = yolo_weights_fallback

    try:
        model = YOLO(weights_path)
        _yolo_model_cache[cache_key] = model
        print("[INFO] YOLO model loaded successfully.")
        return model
    except Exception as e:
        if weights_path == yolo_weights_local:
            print(f"[WARN] Local YOLO weights failed to load: {e}")
            try:
                bad_path = yolo_weights_local + ".bad"
                os.replace(yolo_weights_local, bad_path)
                print(f"[WARN] Renamed invalid local weights to: {bad_path}")
            except Exception:
                pass
            print(f"[INFO] Retrying with fallback weights: {yolo_weights_fallback}")
            model = YOLO(yolo_weights_fallback)
            _yolo_model_cache[cache_key] = model
            print("[INFO] YOLO fallback model loaded successfully.")
            return model
        raise RuntimeError(f"[ERROR] Failed to load YOLO model: {e}")


def load_grounding_dino(device: str, model_id: str = GROUNDING_DINO_MODEL_ID_DEFAULT):
    global _grounding_processor_cache, _grounding_model_cache, _grounding_model_cache_key

    if not GROUNDING_DINO_AVAILABLE:
        raise RuntimeError("transformers is not installed. Install with: pip install transformers")

    cache_key = (device, model_id)
    if _grounding_model_cache is not None and _grounding_processor_cache is not None and _grounding_model_cache_key == cache_key:
        return _grounding_processor_cache, _grounding_model_cache

    print(f"[INFO] Loading Grounding DINO model: {model_id}")
    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(model_id)
    model.to(device)
    model.eval()

    _grounding_processor_cache = processor
    _grounding_model_cache = model
    _grounding_model_cache_key = cache_key
    print("[INFO] Grounding DINO loaded successfully.")
    return processor, model


@torch.no_grad()
def run_grounding_dino_single(
    rgb: np.ndarray,
    target_label: str,
    device: str,
    model_id: str = GROUNDING_DINO_MODEL_ID_DEFAULT,
    box_threshold: float = GROUNDING_DINO_BOX_THRESHOLD_DEFAULT,
    text_threshold: float = GROUNDING_DINO_TEXT_THRESHOLD_DEFAULT,
) -> List[Tuple[str, List[float], float]]:
    """
    Returns detections as [(label, [x1,y1,x2,y2], score), ...]
    Uses a text prompt for a single known target object.
    """
    try:
        processor, model = load_grounding_dino(device=device, model_id=model_id)
    except Exception as e:
        print(f"[WARN] Grounding DINO unavailable: {e}")
        return []

    if Image is None:
        print("[WARN] Pillow not available; Grounding DINO skipped.")
        return []

    prompt = target_label.strip()
    if not prompt.endswith("."):
        prompt = prompt + "."

    try:
        pil_img = Image.fromarray(rgb)
        inputs = processor(images=pil_img, text=prompt, return_tensors="pt")
        inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}

        outputs = model(**inputs)
        post_fn = processor.post_process_grounded_object_detection
        sig = inspect.signature(post_fn)

        kwargs = {
            "outputs": outputs,
            "input_ids": inputs["input_ids"],
            "text_threshold": text_threshold,
            "target_sizes": [pil_img.size[::-1]],
        }

        if "box_threshold" in sig.parameters:
            kwargs["box_threshold"] = box_threshold
        elif "threshold" in sig.parameters:
            kwargs["threshold"] = box_threshold
        else:
            kwargs["threshold"] = box_threshold

        results = post_fn(**kwargs)
    except Exception as e:
        print(f"[WARN] Grounding DINO inference failed for '{target_label}': {e}")
        return []

    if not results:
        return []

    result = results[0]
    boxes = result.get("boxes", [])
    scores = result.get("scores", [])
    labels = result.get("labels", [])

    dets: List[Tuple[str, List[float], float]] = []
    for box, score, label in zip(boxes, scores, labels):
        xyxy = box.detach().cpu().numpy().astype(float).tolist() if hasattr(box, "detach") else list(map(float, box))
        score_val = float(score.detach().cpu().item()) if hasattr(score, "detach") else float(score)
        label_str = str(label)
        dets.append((label_str, xyxy, score_val))
    return dets


def rembg_fallback_cutout(
    image_path: str,
    out_dir: str,
    base: str,
    crop_pad: int = 8,
    alpha_thresh: int = 10,
) -> int:
    if not REMBG_AVAILABLE:
        print("[WARN] rembg fallback requested but rembg/Pillow not installed.")
        return 0

    try:
        with Image.open(image_path) as im:
            im = im.convert("RGBA")
            out = rembg_remove(im)
            if isinstance(out, (bytes, bytearray)):
                out = Image.open(io.BytesIO(out)).convert("RGBA")
            elif isinstance(out, Image.Image):
                out = out.convert("RGBA")
            else:
                out = Image.open(io.BytesIO(out)).convert("RGBA")
    except Exception as e:
        print(f"[WARN] rembg failed on {image_path}: {e}")
        return 0

    rgba = np.array(out)
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        print(f"[WARN] rembg output unexpected shape: {getattr(rgba, 'shape', None)}")
        return 0

    alpha = rgba[:, :, 3]
    mask = (alpha > alpha_thresh).astype(np.uint8) * 255
    if np.count_nonzero(mask) < 50:
        print("[WARN] rembg produced near-empty alpha; skipping fallback save.")
        return 0

    bgr = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2BGR)
    crop_bgr, crop_mask = tight_crop_by_mask(bgr, mask, pad=crop_pad)

    white_bgr = to_white_bg(crop_bgr, crop_mask)
    cutout_bgra = to_rgba_cutout(crop_bgr, crop_mask)

    white_path = os.path.join(out_dir, f"{base}_fallback_white.png")
    cutout_path = os.path.join(out_dir, f"{base}_fallback_cutout.png")

    cv2.imwrite(white_path, white_bgr)
    cv2.imwrite(cutout_path, cutout_bgra)

    print(f"[OK] Fallback saved: {white_path}")
    print(f"[OK] Fallback saved: {cutout_path}")
    return 1


def save_mask_outputs(
    bgr: np.ndarray,
    mask: np.ndarray,
    out_dir: str,
    base: str,
    name_stem: str,
    crop_pad: int = 8,
) -> int:
    crop_bgr, crop_mask = tight_crop_by_mask(bgr, mask, pad=crop_pad)
    white_bgr = to_white_bg(crop_bgr, crop_mask)
    cutout_bgra = to_rgba_cutout(crop_bgr, crop_mask)

    white_path = os.path.join(out_dir, f"{base}_{name_stem}_white.png")
    cutout_path = os.path.join(out_dir, f"{base}_{name_stem}_cutout.png")

    cv2.imwrite(white_path, white_bgr)
    cv2.imwrite(cutout_path, cutout_bgra)

    print(f"[OK] Saved: {white_path}")
    print(f"[OK] Saved: {cutout_path}")
    return 1


def process_one_image_yolo(
    image_path: str,
    out_dir: str,
    yolo: YOLO,
    predictor: SamPredictor,
    allowed_coco: Set[str],
    crop_pad: int = 8,
) -> int:
    bgr = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if bgr is None:
        print(f"[WARN] Could not read image: {image_path}")
        return 0

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    dets = run_yolo_multi(yolo=yolo, rgb=rgb, allowed_coco=allowed_coco)
    if not dets:
        return 0

    saved = 0
    base = os.path.splitext(os.path.basename(image_path))[0]

    for idx, (cls_name, xyxy, _conf) in enumerate(dets, start=1):
        mask = segment_with_sam(predictor=predictor, rgb=rgb, box_xyxy=xyxy)
        if mask is None:
            continue

        saved += save_mask_outputs(
            bgr=bgr,
            mask=mask,
            out_dir=out_dir,
            base=base,
            name_stem=f"{cls_name}_{idx:02d}",
            crop_pad=crop_pad,
        )
        time.sleep(random.uniform(0.05, 0.15))

    return saved


def process_one_image_grounding_dino(
    image_path: str,
    out_dir: str,
    predictor: SamPredictor,
    item_key: str,
    device: str,
    crop_pad: int = 8,
    grounding_model_id: str = GROUNDING_DINO_MODEL_ID_DEFAULT,
    grounding_box_threshold: float = GROUNDING_DINO_BOX_THRESHOLD_DEFAULT,
    grounding_text_threshold: float = GROUNDING_DINO_TEXT_THRESHOLD_DEFAULT,
) -> int:
    bgr = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if bgr is None:
        print(f"[WARN] Could not read image: {image_path}")
        return 0

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    prompt = get_grounding_prompt(item_key)
    dets = run_grounding_dino_single(
        rgb=rgb,
        target_label=prompt,
        device=device,
        model_id=grounding_model_id,
        box_threshold=grounding_box_threshold,
        text_threshold=grounding_text_threshold,
    )
    if not dets:
        return 0

    best = choose_best_detection(dets)
    if best is None:
        return 0

    label_str, xyxy, conf = best
    mask = segment_with_sam(predictor=predictor, rgb=rgb, box_xyxy=xyxy)
    if mask is None:
        return 0

    base = os.path.splitext(os.path.basename(image_path))[0]
    safe_label = clean_name(label_str) or clean_name(item_key) or "gdino"
    print(f"[INFO] Grounding DINO selected '{label_str}' with score={conf:.4f}")
    return save_mask_outputs(
        bgr=bgr,
        mask=mask,
        out_dir=out_dir,
        base=base,
        name_stem=f"{safe_label}_gdino",
        crop_pad=crop_pad,
    )


def generate_cutouts(
    dataset_dir: str = DATASET_DIR_DEFAULT,
    sam_checkpoint: str = SAM_CHECKPOINT_DEFAULT,
    sam_type: str = SAM_TYPE_DEFAULT,
    yolo_weights_local: str = YOLO_WEIGHTS_LOCAL_DEFAULT,
    yolo_weights_fallback: str = YOLO_WEIGHTS_FALLBACK_DEFAULT,
    force_cpu: bool = False,
    use_grounding_dino_fallback: bool = True,
    use_rembg_fallback: bool = True,
    crop_pad: int = 8,
    grounding_model_id: str = GROUNDING_DINO_MODEL_ID_DEFAULT,
    grounding_box_threshold: float = GROUNDING_DINO_BOX_THRESHOLD_DEFAULT,
    grounding_text_threshold: float = GROUNDING_DINO_TEXT_THRESHOLD_DEFAULT,
) -> Dict[str, int]:
    """
    Returns:
      {
        "processed_folders": X,
        "skipped_folders": Y,
        "total_cutouts": Z,
        "grounding_dino_cutouts": G,
        "fallback_cutouts": F,
      }

    Stages:
      1) YOLO + SAM
      2) Grounding DINO + SAM
      3) rembg
    """
    ensure_file_exists(sam_checkpoint, "SAM checkpoint not found. Put it in models/ as planned.")

    device = "cpu" if force_cpu else ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[INFO] Cutouts: Device = {device}")

    if use_grounding_dino_fallback and not GROUNDING_DINO_AVAILABLE:
        print("[WARN] use_grounding_dino_fallback=True but transformers is not available. Install: pip install transformers")

    if use_rembg_fallback and not REMBG_AVAILABLE:
        print("[WARN] use_rembg_fallback=True but rembg not available. Install: pip install rembg pillow")

    yolo = load_yolo_with_fallback(yolo_weights_local, yolo_weights_fallback)

    sam = sam_model_registry[sam_type](checkpoint=sam_checkpoint)
    sam.to(device=device)
    predictor = SamPredictor(sam)

    processed = 0
    skipped = 0
    total_saved = 0
    grounding_saved = 0
    fallback_saved = 0

    if not os.path.exists(dataset_dir):
        raise FileNotFoundError(f"Dataset dir not found: {dataset_dir}")

    for folder in os.listdir(dataset_dir):
        p = os.path.join(dataset_dir, folder)
        if not os.path.isdir(p):
            continue

        img_path = os.path.join(p, "image.png")
        if not os.path.exists(img_path):
            continue

        out_dir = os.path.join(p, "cutouts")
        os.makedirs(out_dir, exist_ok=True)

        item_key = normalize_item(folder)
        coco_class = FURNITURE_TO_COCO.get(item_key)
        base = os.path.splitext(os.path.basename(img_path))[0]
        processed += 1

        # Stage 1: YOLO + SAM only when there is a COCO mapping.
        n = 0
        if coco_class is not None:
            allowed_for_this = {coco_class}
            print(f"\n[PROCESS] {folder} (YOLO/COCO class = {coco_class}) -> {out_dir}")
            n = process_one_image_yolo(
                image_path=img_path,
                out_dir=out_dir,
                yolo=yolo,
                predictor=predictor,
                allowed_coco=allowed_for_this,
                crop_pad=crop_pad,
            )
            total_saved += n
            if n > 0:
                continue
            print(f"[WARN] YOLO found no '{coco_class}' for '{folder}'")
        else:
            print(f"\n[INFO] {folder} not in COCO mapping, skipping YOLO and trying fallbacks.")

        # Stage 2: Grounding DINO + SAM
        n_gd = 0
        if use_grounding_dino_fallback:
            print(f"[FALLBACK-1] Trying Grounding DINO for '{folder}' -> {out_dir}")
            n_gd = process_one_image_grounding_dino(
                image_path=img_path,
                out_dir=out_dir,
                predictor=predictor,
                item_key=item_key,
                device=device,
                crop_pad=crop_pad,
                grounding_model_id=grounding_model_id,
                grounding_box_threshold=grounding_box_threshold,
                grounding_text_threshold=grounding_text_threshold,
            )
            total_saved += n_gd
            grounding_saved += n_gd
            if n_gd > 0:
                continue
            print(f"[WARN] Grounding DINO produced no cutout for '{folder}'")

        # Stage 3: rembg fallback
        n_fb = 0
        if use_rembg_fallback:
            print(f"[FALLBACK-2] Trying rembg for '{folder}' -> {out_dir}")
            n_fb = rembg_fallback_cutout(img_path, out_dir, base=base, crop_pad=crop_pad)
            total_saved += n_fb
            fallback_saved += n_fb
            if n_fb > 0:
                continue
            print(f"[WARN] rembg produced no cutout for '{folder}'")

        skipped += 1

    return {
        "processed_folders": processed,
        "skipped_folders": skipped,
        "total_cutouts": total_saved,
        "grounding_dino_cutouts": grounding_saved,
        "fallback_cutouts": fallback_saved,
    }


# Backwards compatible name (if you were using run_on_dataset before)
def run_on_dataset(dataset_dir: str = DATASET_DIR_DEFAULT):
    return generate_cutouts(dataset_dir=dataset_dir)


if __name__ == "__main__":
    generate_cutouts()
