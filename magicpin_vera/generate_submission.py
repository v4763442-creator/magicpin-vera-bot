"""
Generate official submission.jsonl from expanded/test_pairs.json.
Runs the official compose() function across all 30 canonical test pairs.
"""

from __future__ import annotations
import json
from pathlib import Path
from magicpin_vera.message_composer import compose


BASE_DIR = Path(__file__).resolve().parent.parent
EXPANDED_DIR = BASE_DIR / "challenge_pack" / "expanded"
OUTPUT_FILE = Path(__file__).resolve().parent / "submission.jsonl"


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_submission():
    test_pairs_path = EXPANDED_DIR / "test_pairs.json"
    if not test_pairs_path.exists():
        raise FileNotFoundError(f"test_pairs.json not found at {test_pairs_path}")

    pairs_data = load_json(test_pairs_path)["pairs"]
    print(f"Loaded {len(pairs_data)} test pairs from {test_pairs_path}")

    lines = []
    for pair in pairs_data:
        test_id = pair["test_id"]
        trigger_id = pair["trigger_id"]
        merchant_id = pair["merchant_id"]
        customer_id = pair.get("customer_id")

        trg_path = EXPANDED_DIR / "triggers" / f"{trigger_id}.json"
        mer_path = EXPANDED_DIR / "merchants" / f"{merchant_id}.json"

        trigger = load_json(trg_path)
        merchant = load_json(mer_path)
        
        cat_slug = merchant.get("category_slug", "dentists")
        cat_path = EXPANDED_DIR / "categories" / f"{cat_slug}.json"
        category = load_json(cat_path)

        customer = None
        if customer_id:
            cus_path = EXPANDED_DIR / "customers" / f"{customer_id}.json"
            if cus_path.exists():
                customer = load_json(cus_path)

        result = compose(category, merchant, trigger, customer)

        row = {
            "test_id": test_id,
            "body": result["body"],
            "cta": result["cta"],
            "send_as": result["send_as"],
            "suppression_key": result["suppression_key"],
            "rationale": result["rationale"]
        }
        lines.append(json.dumps(row, ensure_ascii=False))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Successfully generated {len(lines)} submission lines to {OUTPUT_FILE}")


if __name__ == "__main__":
    generate_submission()
