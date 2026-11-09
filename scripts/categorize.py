"""Categorize new videos with Gemini, constrained to the existing taxonomy."""
import json
import re
import time

FALLBACK = ("Other / General", "General")
# Tried in order. Set the GEMINI_MODEL repo variable to put your own choice first.
DEFAULT_MODELS = ["gemini-3.5-flash", "gemini-3-flash", "gemini-2.5-flash"]
BATCH = 20


def valid_pairs(taxonomy):
    return {(c["name"], s) for c in taxonomy["categories"] for s in c["subcategories"]}


def build_prompt(batch, taxonomy, existing):
    examples = {}
    for v in existing:
        examples.setdefault((v["category"], v["subcategory"]), [])
        if len(examples[(v["category"], v["subcategory"])]) < 2:
            examples[(v["category"], v["subcategory"])].append(v["title"])
    lines = []
    for c in taxonomy["categories"]:
        lines.append(f"- {c['name']}")
        for s in c["subcategories"]:
            ex = "; ".join(f'"{t[:70]}"' for t in examples.get((c["name"], s), []))
            lines.append(f"    - {s}" + (f"   e.g. {ex}" if ex else ""))
    videos = [
        {"id": v["id"], "title": v["title"], "channel": v["channel"],
         "description": v["description"][:400]}
        for v in batch
    ]
    return (
        "You organize a personal library of developer-learning YouTube videos.\n"
        "For each video pick exactly ONE category and ONE of that category's subcategories "
        "from the list below. Use only listed names, spelled exactly. If nothing fits, use "
        f"category '{FALLBACK[0]}' with subcategory '{FALLBACK[1]}'.\n\n"
        "Taxonomy:\n" + "\n".join(lines) + "\n\nVideos:\n"
        + json.dumps(videos, ensure_ascii=False, indent=1)
        + "\n\nReturn a JSON array with one object per video: "
        '{"id": ..., "category": ..., "subcategory": ...}.'
    )


def build_schema(taxonomy):
    cats = [c["name"] for c in taxonomy["categories"]]
    subs = sorted({s for c in taxonomy["categories"] for s in c["subcategories"]})
    return {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "id": {"type": "STRING"},
                "category": {"type": "STRING", "enum": cats},
                "subcategory": {"type": "STRING", "enum": subs},
            },
            "required": ["id", "category", "subcategory"],
        },
    }


def gemini_generate(api_key):
    """Return run(model, prompt, schema) -> JSON text, using the google-genai SDK."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    def run(model, prompt, schema):
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0,
            ),
        )
        return resp.text

    return run


def _parse(text):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("expected a JSON array")
    return {d["id"]: (d["category"], d["subcategory"]) for d in data if isinstance(d, dict) and "id" in d}


def categorize(new_videos, taxonomy, existing, generate, models=None, sleep=time.sleep, log=print):
    """Return {video_id: (category, subcategory)}. Never raises: falls back to FALLBACK."""
    result = {}
    pairs, schema = valid_pairs(taxonomy), build_schema(taxonomy)
    models = [m for m in (models or DEFAULT_MODELS) if m]
    if generate is None:
        log("WARNING: no Gemini key, so new videos go to the fallback category.")
        return {v["id"]: FALLBACK for v in new_videos}
    working = None
    for i in range(0, len(new_videos), BATCH):
        batch = new_videos[i : i + BATCH]
        prompt = build_prompt(batch, taxonomy, existing)
        parsed = None
        for model in ([working] if working else []) + [m for m in models if m != working]:
            for attempt in range(1, 4):
                try:
                    parsed = _parse(generate(model, prompt, schema))
                    working = model
                    break
                except Exception as exc:  # noqa: BLE001
                    log(f"Gemini '{model}' attempt {attempt} failed: {exc}")
                    text = str(exc).lower()
                    if "not found" in text or "404" in text or "not supported" in text:
                        break  # wrong model name -> try the next one
                    if attempt < 3:
                        sleep(2 ** attempt * 3)
            if parsed is not None:
                break
        parsed = parsed or {}
        for v in batch:
            pair = tuple(parsed.get(v["id"], ())) or None
            if pair in pairs:
                result[v["id"]] = pair
            else:
                log(f"WARNING: no valid category for '{v['title']}' -> {FALLBACK[0]} / {FALLBACK[1]}")
                result[v["id"]] = FALLBACK
    return result
