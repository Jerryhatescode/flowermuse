import json
import requests
from flask import Flask, render_template, abort, redirect, url_for

app = Flask(__name__)

UNSPLASH_ACCESS_KEY = "kIepgUi_TYVu85KiJmV6a5vTrnowvLu-Nh1fX7FowbU"  # <-- put your real key here

# Load flower JSON (must contain the full list, not a sliced 10-item file)
with open("list.json", "r", encoding="utf-8") as f:
    flowers = json.load(f)

NEGATIVE_TERMS = {
    "insect","bug","bee","butterfly","wasp","grasshopper","locust","spider","moth"
}
TIMEOUT = 12

def normalize_name(name: str) -> str:
    n = (name or "").lower()
    n = n.replace("orchit", "orchid")  # fix common typo
    # strip bracketed aliases like "Belladonna (Deadly Nightshade)"
    if "(" in n and ")" in n:
        import re
        n = re.sub(r"\s*\(.*?\)\s*", " ", n)
    return " ".join(n.split())

def expected_terms_from(name: str, scientific: str | None) -> set:
    base = set()
    lower = f"{name} {scientific or ''}".lower()
    for kw in [
        "orchid","rose","lily","lotus","jasmine","tulip","hibiscus",
        "sunflower","marigold","dahlia","magnolia","plumeria",
        "peony","lavender","camellia","cactus","cereus","night"
    ]:
        if kw in lower:
            base.add(kw)
    base |= {"flower","blossom","bloom","petal","inflorescence"}
    return base

def choose_best_photo(items, expected_terms: set):
    def score(item):
        text_parts = [
            item.get("alt_description") or "",
            item.get("description") or "",
            " ".join(t.get("title","") for t in item.get("tags", []))
        ]
        text = " ".join(text_parts).lower()
        if any(bad in text for bad in NEGATIVE_TERMS):
            return -999
        s = 0
        for term in expected_terms:
            if term in text:
                s += 3
        for good in ["flower","blossom","bloom","orchid","petal","flora","botany","plant"]:
            if good in text:
                s += 1
        return s

    if not items:
        return ""
    items_sorted = sorted(items, key=score, reverse=True)
    chosen = items_sorted[0]
    raw = chosen["urls"]["raw"]
    return f"{raw}&w=400&h=400&fit=crop"  # square thumbnail

def search_unsplash(query: str, expected_terms: set) -> str:
    url = "https://api.unsplash.com/search/photos"
    params = {
        "query": query,
        "per_page": 10,
        "orientation": "squarish",
        "content_filter": "high",
        "order_by": "relevant",
        "client_id": UNSPLASH_ACCESS_KEY,
    }
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        print("UNSPLASH", r.status_code, r.url)
        if r.status_code != 200:
            print("Response snippet:", r.text[:200])
            return ""
        data = r.json()
        return choose_best_photo(data.get("results", []), expected_terms)
    except Exception as e:
        print("Unsplash error:", e)
        return ""

def fetch_photo_for_flower(flower: dict) -> str:
    name = normalize_name(flower.get("name",""))
    sci  = (flower.get("scientific_name") or "").strip()
    expected = expected_terms_from(name, sci)

    candidates = [
        f"{name} flower",
        f"{sci} flower" if sci else "",
        f"{name} plant",
    ]
    for q in [c for c in candidates if c]:
        url = search_unsplash(q, expected)
        if url:
            return url
    return "https://via.placeholder.com/400"

def save_json():
    with open("list.json", "w", encoding="utf-8") as f:
        json.dump(flowers, f, indent=2, ensure_ascii=False)

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/flowers")
def flower_list():
    changed = False
    for f in flowers:
        if not f.get("image_url"):  # only fetch once per flower
            f["image_url"] = fetch_photo_for_flower(f)
            changed = True
    if changed:
        save_json()
    return render_template("flower_list.html", flowers=flowers)

@app.route("/flower/<int:flower_id>")
def flower_detail(flower_id):
    flower = next((f for f in flowers if f["id"] == flower_id), None)
    if not flower:
        abort(404)

    if not flower.get("image_url"):
        flower["image_url"] = fetch_photo_for_flower(flower)
        save_json()

    # compute prev/next inside the route
    ids = [f["id"] for f in flowers]
    try:
        idx = ids.index(flower_id)
    except ValueError:
        idx = None

    prev_id = flowers[idx - 1]["id"] if idx is not None and idx > 0 else None
    next_id = flowers[idx + 1]["id"] if idx is not None and idx < len(flowers) - 1 else None

    return render_template("flower_detail.html", flower=flower, prev_id=prev_id, next_id=next_id)

@app.route("/refresh-image/<int:flower_id>")
def refresh_image(flower_id):
    flower = next((f for f in flowers if f["id"] == flower_id), None)
    if not flower:
        abort(404)
    flower["image_url"] = fetch_photo_for_flower(flower)
    save_json()
    return redirect(url_for("flower_detail", flower_id=flower_id))

if __name__ == "__main__":
    app.run(debug=True)
