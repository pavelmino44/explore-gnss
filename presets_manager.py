import json
import os
from pathlib import Path

PRESETS_DIR = Path("presets")
PRESETS_DIR.mkdir(exist_ok=True)

def list_presets():
    files = [f.stem for f in PRESETS_DIR.glob("*.json")]
    return files

def load_preset(name):
    path = PRESETS_DIR / f"{name}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_preset(data, name):
    path = PRESETS_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def delete_preset(name):
    path = PRESETS_DIR / f"{name}.json"
    if path.exists():
        os.remove(path)