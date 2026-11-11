import json, re, shutil
from pathlib import Path

SRC = Path("bli_disability")
WEB = Path("web")
(WEB / "images").mkdir(parents=True, exist_ok=True)

tree = json.load(open(SRC / "disability_tree.json", encoding="utf-8"))


def safe_name(name):
    return re.sub(r"[^\w.\-]", "_", name)


def collect(node, sections):
    if node["records"]:
        imgs = []
        for im in node["images"]:
            src = SRC / "images" / Path(im["local"]).name
            if src.exists():
                dst_name = safe_name(src.name)
                shutil.copy(src, WEB / "images" / dst_name)
                imgs.append("images/" + dst_name)
        groups = {}
        for r in node["records"]:
            groups.setdefault(r["group"], []).append({
                "description": r["description"],
                "normal_days": r["normal_days"],
                "occupational_days": r["occupational_days"],
            })
        sections.append({
            "title": node["title"],
            "path": node["path"],
            "images": imgs,
            "updated": node["updated"],
            "url": node["url"],
            "groups": [{"name": k, "records": v} for k, v in groups.items()],
        })
    for c in node["children"]:
        collect(c, sections)


data = []
for top in tree:
    sections = []
    collect(top, sections)
    data.append({
        "name": top["title"],
        "count": sum(len(r["records"]) for s in sections for r in s["groups"]),
        "sections": sections,
    })

(WEB / "disability.json").write_text(
    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# 3D 熱點對照表範本（之後手動填）
map_path = WEB / "body_map.json"
if not map_path.exists():
    template = {d["name"]: {"meshes": [], "label_position": [0, 0, 0]} for d in data}
    map_path.write_text(json.dumps(template, ensure_ascii=False, indent=2),
                        encoding="utf-8")

for d in data:
    print(f"{d['name']}: {d['count']} 筆，{len(d['sections'])} 個子頁")
print("輸出在", WEB.resolve())
(WEB / "disability.js").write_text(
    "const DISABILITY = " + json.dumps(data, ensure_ascii=False) + ";", encoding="utf-8")