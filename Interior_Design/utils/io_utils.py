import os

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def save_lines(path: str, lines):
    parent = os.path.dirname(path)
    if parent:
        ensure_dir(parent)
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(str(line).strip() + "\n")