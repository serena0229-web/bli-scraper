import csv, json, re, time
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup

BASE = "https://www.bli.gov.tw"
START = BASE + "/0005867.html"
OUT = Path("bli_disability")
IMG_DIR = OUT / "images"
RAW_DIR = OUT / "raw"
for d in (IMG_DIR, RAW_DIR):
    d.mkdir(parents=True, exist_ok=True)

WANT = ["眼", "鼻", "口", "上肢", "軀幹", "下肢",
        "精神神經", "耳", "頭臉頸", "胸腹部臟器", "皮膚"]

# 若自動抓不到 11 項，把網址手動填在這裡（格式：("眼", "https://www.bli.gov.tw/xxxx.html")）
MANUAL_CATEGORIES = []

session = requests.Session()
session.headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
seen = set()

RE_N = re.compile(r"普通給付日數\s*(\d+)\s*日")
RE_J = re.compile(r"職災給付日數\s*(\d+)\s*日")
RE_UPDATED = re.compile(r"最後更新日期[：:]\s*([\d\-]+)")


def page_id(url):
    return Path(urlparse(url).path).stem


def get_soup(url):
    time.sleep(1)  # 禮貌：每次請求間隔 1 秒
    r = session.get(url, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"
    (RAW_DIR / f"{page_id(url)}.html").write_text(r.text, encoding="utf-8")
    return BeautifulSoup(r.text, "html.parser")


def get_children(soup):
    """內容區 div.multilevel 底下的子項連結"""
    result, urls = [], set()
    for a in soup.select("div.multilevel a[href]"):
        href = a["href"]
        if href.startswith(("#", "javascript")) or ".html" not in href:
            continue
        url = urljoin(BASE, href)
        if url not in urls:
            urls.add(url)
            result.append((a.get_text(strip=True), url))
    return result


def get_categories_by_text(soup):
    """備用：用連結文字比對 11 個種類，不依賴 HTML 結構"""
    found = {}
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        if text in WANT and text not in found and ".html" in a["href"]:
            found[text] = urljoin(BASE, a["href"])
    return [(n, found[n]) for n in WANT if n in found]


def get_categories(soup):
    if MANUAL_CATEGORIES:
        return MANUAL_CATEGORIES
    cats = get_children(soup)
    if len(cats) != 11:
        print(f"內容區找到 {len(cats)} 項，改用連結文字比對")
        cats = get_categories_by_text(soup)
    return cats


def download_image(src, pid):
    url = urljoin(BASE, src)
    name = f"{pid}_{unquote(Path(urlparse(url).path).name)}"
    path = IMG_DIR / name
    if not path.exists():
        time.sleep(0.5)
        r = session.get(url, timeout=30)
        r.raise_for_status()
        path.write_bytes(r.content)
    return {"src": url, "local": str(path)}


def extract_records(lines):
    """把『…－普通給付日數1000日 職災給付日數1500日』拆成結構化欄位"""
    records, group = [], ""
    for ln in lines:
        n, j = RE_N.search(ln), RE_J.search(ln)
        if n or j:
            desc = re.split(r"[－\-–—]+\s*普通給付日數", ln)[0].strip()
            records.append({
                "group": group,
                "description": desc,
                "normal_days": int(n.group(1)) if n else None,
                "occupational_days": int(j.group(1)) if j else None,
                "raw": ln,
            })
        elif len(ln) <= 12 and not ln.startswith("*"):
            group = ln  # 例如「一、兩眼」「二、單眼」
    return records


def crawl(name, url, path, depth=0):
    if url in seen or depth > 5:
        return None
    seen.add(url)
    soup = get_soup(url)
    pid = page_id(url)

    h1 = soup.select_one("div.title h1")
    title = h1.get_text(strip=True) if h1 else name
    node = {"title": title, "url": url, "path": path + [title],
            "images": [], "lines": [], "records": [],
            "updated": None, "children": []}

    m = RE_UPDATED.search(soup.get_text())
    if m:
        node["updated"] = m.group(1)

    ta = soup.select_one("div.text-area")
    if ta:
        for img in ta.select("img[src]"):
            node["images"].append({**download_image(img["src"], pid),
                                   "alt": img.get("alt", "")})
        node["lines"] = [l for l in ta.get_text("\n", strip=True).split("\n") if l]
        node["records"] = extract_records(node["lines"])

    kids = get_children(soup)
    print("  " * depth +
          f"{title}  子項:{len(kids)}  圖:{len(node['images'])}  等級資料:{len(node['records'])}")
    for cname, curl in kids:
        child = crawl(cname, curl, node["path"], depth + 1)
        if child:
            node["children"].append(child)
    return node


def flatten(node, rows):
    for r in node["records"]:
        rows.append({
            "category": node["path"][0] if node["path"] else "",
            "path": " > ".join(node["path"]),
            "group": r["group"],
            "description": r["description"],
            "normal_days": r["normal_days"],
            "occupational_days": r["occupational_days"],
            "images": ";".join(i["local"] for i in node["images"]),
            "url": node["url"],
            "updated": node["updated"],
        })
    for c in node["children"]:
        flatten(c, rows)


def main():
    soup = get_soup(START)
    print("起點頁標題:", soup.title.get_text(strip=True) if soup.title else None)
    print("起點頁含『皮膚』:", "皮膚" in soup.get_text())

    cats = get_categories(soup)
    print(f"找到 {len(cats)} 個失能種類（預期 11）")
    for n, u in cats:
        print("  ", n, u)

    if not cats:
        print("⚠ 一個都沒找到。")
        print("  若上面『含皮膚』是 False：選單由 JavaScript 載入，請回報給我。")
        print("  若是 True：打開 bli_disability/raw/0005867.html 搜尋『皮膚』，把附近 HTML 貼給我。")
        return
    if len(cats) != 11:
        print("⚠ 數量不是 11，缺少的種類請用 MANUAL_CATEGORIES 手動補。")

    tree = []
    for name, url in cats:
        node = crawl(name, url, [])
        if node:
            tree.append(node)

    (OUT / "disability_tree.json").write_text(
        json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = []
    for n in tree:
        flatten(n, rows)
        fields = ["category", "path", "group", "description", "normal_days", "occupational_days", "images", "url", "updated"]
    with open(OUT / "disability_flat.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"完成：{len(rows)} 筆等級資料，輸出在 {OUT.resolve()}")


if __name__ == "__main__":
    main()