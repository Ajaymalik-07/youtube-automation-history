import json
import os
from gui import _build_description, _with_credit
from apis import seo

def update_seo():
    script_file = "output/script.json"
    with open(script_file, encoding="utf-8") as f:
        s = json.load(f)

    research_file = "output/research.json"
    with open(research_file, encoding="utf-8") as f:
        r = json.load(f)

    # 100/100 Title: 65 chars, includes 5000 (digits), Lost Saraswati River, Indus Valley Civilization
    # Perfectly fits between 30 and 70 chars
    new_title = "The Lost Saraswati River & Indus Valley Civilization (5000 Years)"
    s["title"] = new_title

    # Rich 100/100 Description
    opening = (
        "Did the lost Saraswati River cause the silent collapse of the Indus Valley Civilization? "
        "5,000 years ago, a colossal empire flourished before vanishing under the Thar desert sands.\n\n"
    )
    built = _build_description(s, r, "normal")
    full_desc = _with_credit(opening + built)
    s["description"] = full_desc

    with open(script_file, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)

    # Update library project
    lib_dir = os.path.join("output", "library", "20261028-170406-lost-civilization-under-desert")
    if os.path.isdir(lib_dir):
        lib_meta_file = os.path.join(lib_dir, "meta.json")
        with open(lib_meta_file, encoding="utf-8") as f:
            m = json.load(f)
        m["title"] = new_title
        m["description"] = full_desc
        with open(lib_meta_file, "w", encoding="utf-8") as f:
            json.dump(m, f, indent=2, ensure_ascii=False)

        with open(os.path.join(lib_dir, "script.json"), "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2, ensure_ascii=False)

    # Check score
    score_res = seo.score(new_title, full_desc, s.get("tags", []), r.get("topic", ""), is_shorts=False)
    print("NEW SEO SCORE:", score_res["score"], "/ 100")
    print("GRADE:", score_res["grade"])
    for c in score_res["checks"]:
        print(f"[{'PASS' if c['ok'] else 'FAIL'}] {c['label']} ({c['weight']} pts)")

if __name__ == "__main__":
    update_seo()
