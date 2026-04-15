import json
import time
import cohere
from utils.io_utils import save_lines

ALLOWED_KEYWORDS = [
    "bed", "chair", "table", "desk", "wardrobe",
    "sofa", "cabinet", "bookshelf", "dresser",
    "nightstand", "bench"
]

def safe_cohere_chat(co: cohere.Client, prompt: str, retries=3):
    for attempt in range(retries):
        try:
            response = co.chat(
                model="command-r-08-2024",
                message=prompt,
                temperature=0.3,
            )
            return response.text.strip()
        except Exception as e:
            print(f"⚠ Attempt {attempt+1} failed: {e}")
            time.sleep(2)

    print("❌ Cohere API failed after retries.")
    return None

def generate_furniture_only(co: cohere.Client, room_type: str, style: str, budget_level: str):
    prompt = f"""
You are a professional interior designer.

Suggest ONLY essential furniture items for a {room_type}.
Style: {style}
Budget: {budget_level}

IMPORTANT RULES:
- Include ONLY core furniture.
- Allowed examples: bed, chair, table, desk, wardrobe, sofa, cabinet, bookshelf.
- Do NOT include decor.
- Do NOT include lighting.
- Do NOT include rugs, carpets, curtains, paintings, linens, lamps, accessories.

Respond ONLY in valid JSON.

Format:
{{
  "room_type": "{room_type}",
  "furniture": [
    {{
      "name": ""
    }}
  ]
}}
""".strip()

    response_text = safe_cohere_chat(co, prompt)
    if not response_text:
        return None

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        print("⚠ Invalid JSON received:")
        print(response_text)
        return None

def filter_core_furniture(furniture_list):
    filtered = []
    for item in furniture_list:
        name = (item.get("name") or "").lower().strip()
        if not name:
            continue
        if any(keyword in name for keyword in ALLOWED_KEYWORDS):
            filtered.append(name)
    # dedupe keep order
    out, seen = [], set()
    for x in filtered:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out

def get_furniture_list_and_save(
    room_type: str,
    style: str,
    budget: str,
    out_txt_path: str,
    cohere_api_key: str
):
    co = cohere.Client(api_key=cohere_api_key)

    print("\n🧠 Generating core furniture only...\n")
    room_data = generate_furniture_only(co, room_type, style, budget)

    if not room_data:
        return []

    filtered = filter_core_furniture(room_data.get("furniture", []))
    if not filtered:
        return []

    # Save ONE PER LINE (pipeline-friendly)
    save_lines(out_txt_path, filtered)
    print(f"\n✅ Core furniture list saved to {out_txt_path}")

    return filtered