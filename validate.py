import csv, json
from collections import Counter
from pathlib import Path

OUT = Path("bli_disability")
rows = list(csv.DictReader(open(OUT / "disability_flat.csv", encoding="utf-8-sig")))
tree = json.load(open(OUT / "disability_tree.json", encoding="utf-8"))

print("總筆數:", len(rows))
print("\n== 各類別筆數 ==")
for k, v in Counter(r["category"] for r in rows).items():
    print(f"  {k}: {v}")

print("\n== 缺日數的資料 ==")
bad = [r for r in rows if not r["normal_days"] or not r["occupational_days"]]
print("  筆數:", len(bad))
for r in bad[:10]:
    print("  ", r["path"], "|", r["description"][:30])

print("\n== 職災日數 ≠ 普通日數×1.5（需人工核對）==")
odd = []
for r in rows:
    if r["normal_days"] and r["occupational_days"]:
        if int(r["normal_days"]) * 1.5 != int(r["occupational_days"]):
            odd.append(r)
print("  筆數:", len(odd))
for r in odd[:10]:
    print("  ", r["path"], r["normal_days"], r["occupational_days"])

print("\n== 沒有圖片的頁面 ==")
def walk(n):
    if n["records"] and not n["images"]:
        print("  ", " > ".join(n["path"]))
    for c in n["children"]:
        walk(c)
for n in tree:
    walk(n)

print("\n== 空說明的資料 ==")
print("  ", sum(1 for r in rows if len(r["description"]) < 4))