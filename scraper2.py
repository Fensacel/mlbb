import argparse
import json
import os
import re
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


BASE_WIKI = "https://mobile-legends.fandom.com/wiki/"
API_URL = "https://mobile-legends.fandom.com/api.php"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

NOISY_TITLE_KEYWORDS = (
    "patch notes",
    "update",
    "advance server",
    "events",
)


def normalize_lookup(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def build_wiki_url(title):
    page = quote(str(title).replace(" ", "_"))
    return f"{BASE_WIKI}{page}"


def load_hero_slugs(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("hero.json harus berupa array slug hero.")

    return [str(x).strip() for x in data if str(x).strip()]


def resolve_page_title(slug):
    """Cari judul halaman wiki yang paling cocok untuk slug hero."""
    readable_slug = str(slug).replace("_", " ").replace("-", " ").strip()
    slug_norm = normalize_lookup(readable_slug)

    search_terms = [
        readable_slug,
        readable_slug.title(),
        f'"{readable_slug}"',
    ]

    best_title = None
    best_score = -1

    for term in search_terms:
        params = {
            "action": "query",
            "list": "search",
            "format": "json",
            "srsearch": term,
            "srlimit": 5,
        }
        resp = requests.get(API_URL, params=params, timeout=20)
        resp.raise_for_status()
        payload = resp.json()

        results = payload.get("query", {}).get("search", [])
        if not results:
            continue

        for result in results:
            title = result.get("title", "")
            if not title:
                continue

            title_norm = normalize_lookup(title)
            score = 0

            if title_norm == slug_norm:
                score += 100
            elif slug_norm and slug_norm in title_norm:
                score += 70

            lowered_title = title.lower()
            if any(keyword in lowered_title for keyword in NOISY_TITLE_KEYWORDS):
                score -= 80

            if score > best_score:
                best_score = score
                best_title = title

    if best_title and best_score > 0:
        return best_title

    # Fallback terakhir: ambil title pertama yang bukan patch/update page.
    for term in search_terms:
        params = {
            "action": "query",
            "list": "search",
            "format": "json",
            "srsearch": term,
            "srlimit": 5,
        }
        resp = requests.get(API_URL, params=params, timeout=20)
        resp.raise_for_status()
        payload = resp.json()

        for result in payload.get("query", {}).get("search", []):
            title = result.get("title", "")
            if title and not any(keyword in title.lower() for keyword in NOISY_TITLE_KEYWORDS):
                return title

    return None


def parse_infobox(soup):
    infobox_data = {}

    infobox = soup.select_one("aside.portable-infobox")
    if not infobox:
        return infobox_data

    rows = infobox.select("section.pi-item")
    for row in rows:
        label_el = row.select_one("h3.pi-data-label")
        value_el = row.select_one("div.pi-data-value")
        if not label_el or not value_el:
            continue

        label = " ".join(label_el.get_text(" ", strip=True).split())
        value = " ".join(value_el.get_text(" ", strip=True).split())
        if label and value:
            infobox_data[label] = value

    return infobox_data


def parse_intro(soup):
    content = soup.select_one("div.mw-parser-output")
    if not content:
        return ""

    for p in content.select("p"):
        text = " ".join(p.get_text(" ", strip=True).split())
        if text and len(text) > 60:
            text = re.sub(r"\[[0-9]+\]", "", text)
            return text

    return ""


def clean_text(text):
    return " ".join(text.split()).strip()


def normalize_image_url(img):
    if not img:
        return ""
    url = img.get("data-src") or img.get("src") or ""
    if url.startswith("data:image"):
        return ""
    return url


def parse_properties_table(table):
    rows = table.select("tr")
    if not rows:
        return {}

    headers = [clean_text(x.get_text(" ", strip=True)) for x in rows[0].select("th,td")]
    if not headers or "properties" not in headers[0].lower():
        return {}

    levels = headers[1:]
    properties = {}

    for row in rows[1:]:
        cols = [clean_text(x.get_text(" ", strip=True)) for x in row.select("th,td")]
        if len(cols) < 2:
            continue
        label = cols[0]
        values = cols[1:]
        if levels and len(values) == len(levels):
            properties[label] = dict(zip(levels, values))
        else:
            properties[label] = values

    return properties


def parse_ability_table(table, section):
    name_el = table.select_one("b")
    name = clean_text(name_el.get_text(" ", strip=True)) if name_el else section

    image_el = table.select_one("img")
    image_url = normalize_image_url(image_el)

    tag_items = []
    for span in table.select("td span[style*='background-color']"):
        text = clean_text(span.get_text(" ", strip=True))
        if text and len(text) <= 24:
            tag_items.append(text)

    tags = []
    seen = set()
    for item in tag_items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            tags.append(item)

    info_cells = table.select("tr > td")
    if len(info_cells) >= 2:
        info_clone = BeautifulSoup(str(info_cells[1]), "html.parser")
        for nested in info_clone.select("table"):
            nested.decompose()
        raw_text = clean_text(info_clone.get_text(" ", strip=True))
    else:
        raw_text = clean_text(table.get_text(" ", strip=True))

    desc = raw_text
    if name and desc.lower().startswith(name.lower()):
        desc = clean_text(desc[len(name):])

    return {
        "section": section,
        "name": name,
        "image_url": image_url,
        "tags": tags,
        "description": desc,
        "properties": {},
    }


def parse_abilities(soup):
    content = soup.select_one("div.mw-parser-output") or soup

    abilities_h2 = None
    for h2 in content.select("h2"):
        if "abilities" in clean_text(h2.get_text(" ", strip=True)).lower():
            abilities_h2 = h2
            break

    if not abilities_h2:
        return []

    abilities = []
    current = None
    node = abilities_h2

    while True:
        node = node.find_next_sibling()
        if node is None:
            break
        if node.name == "h2":
            break

        if node.name == "h3":
            section = clean_text(node.get_text(" ", strip=True))
            section = re.sub(r"\[.*?\]", "", section).strip()
            current = {
                "section": section,
                "name": section,
                "image_url": "",
                "tags": [],
                "description": "",
                "properties": {},
            }
            continue

        if node.name == "table" and "wikitable" in (node.get("class") or []):
            if current is None:
                continue

            if not current.get("description"):
                parsed = parse_ability_table(node, current["section"])
                current.update(parsed)
                abilities.append(current)

            if abilities:
                props = {}
                direct_props = parse_properties_table(node)
                if direct_props:
                    props = direct_props
                else:
                    for nested in node.find_all("table"):
                        nested_props = parse_properties_table(nested)
                        if nested_props:
                            props = nested_props
                            break

                if props:
                    abilities[-1]["properties"] = props

    return abilities


def normalize_stat_key(label):
    key = clean_text(label)
    key = re.sub(r"\(.*?\)", "", key)
    key = re.sub(r"[^a-zA-Z0-9]+", "_", key).strip("_").lower()
    return key


def parse_hero_stats(soup):
    content = soup.select_one("div.mw-parser-output") or soup

    for table in content.select("table.wikitable"):
        rows = table.select("tr")
        if len(rows) < 2:
            continue

        header_row_idx = None
        header_text = []
        for idx in range(min(4, len(rows))):
            probe_cells = rows[idx].select("th,td")
            probe_text = [clean_text(c.get_text(" ", strip=True)) for c in probe_cells]
            probe_blob = " ".join(probe_text).lower()
            if "attribute" in probe_blob and ("level 1" in probe_blob or "base stats" in probe_blob):
                header_row_idx = idx
                header_text = probe_text
                break

        looks_like_stats_table = header_row_idx is not None
        if not looks_like_stats_table:
            continue

        headers = []
        for head in header_text:
            if head:
                headers.append(head)

        if not headers:
            continue

        if header_row_idx + 1 < len(rows):
            second_header_cells = rows[header_row_idx + 1].select("th,td")
            second_header = [clean_text(c.get_text(" ", strip=True)) for c in second_header_cells]
            if second_header and any(x for x in second_header if x.lower().startswith("level") or x.lower() == "growth"):
                headers = [headers[0]] + [x for x in second_header if x]

        stats = {}
        data_start_idx = header_row_idx + 1
        # Jika ada subheader level/growth, data mulai dari baris setelahnya.
        if data_start_idx < len(rows):
            probe_cells = [clean_text(c.get_text(" ", strip=True)) for c in rows[data_start_idx].select("th,td")]
            probe_blob = " ".join(probe_cells).lower()
            if any(x in probe_blob for x in ("level 1", "level 15", "growth")):
                data_start_idx += 1

        for row in rows[data_start_idx:]:
            cells = [clean_text(c.get_text(" ", strip=True)) for c in row.select("th,td")]
            cells = [c for c in cells if c]
            if len(cells) < 2:
                continue

            label = cells[0]
            label_lower = label.lower()
            if label_lower in {"attribute", "base stats", "level 1", "level 15", "growth"}:
                continue

            values = cells[1:]
            if not values:
                continue

            stat_key = normalize_stat_key(label)
            if not stat_key:
                continue

            row_data = {}
            if len(headers) > 1:
                value_headers = headers[1:]
                if len(values) == len(value_headers):
                    for idx, val in enumerate(values):
                        row_data[normalize_stat_key(value_headers[idx])] = val
                else:
                    row_data["values"] = values
            else:
                row_data["values"] = values

            stats[stat_key] = {
                "label": label,
                **row_data,
            }

        if stats:
            return stats

    return {}


def fetch_hero_page_html(title):
    """Ambil HTML hero dari API parse; fallback ke halaman langsung jika perlu."""
    url = build_wiki_url(title)

    parse_params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "format": "json",
    }

    try:
        parse_resp = requests.get(API_URL, params=parse_params, headers=HEADERS, timeout=25)
        parse_resp.raise_for_status()
        payload = parse_resp.json()
        html = payload.get("parse", {}).get("text", {}).get("*")
        if html:
            return url, html
    except Exception:
        pass

    resp = requests.get(url, headers=HEADERS, timeout=25)
    resp.raise_for_status()
    return url, resp.text


def scrape_hero(slug):
    title = resolve_page_title(slug)
    if not title:
        return {
            "slug": slug,
            "error": "Halaman tidak ditemukan dari API search.",
        }

    url, html = fetch_hero_page_html(title)
    soup = BeautifulSoup(html, "html.parser")

    name_el = soup.select_one("h1.page-header__title")
    name = name_el.get_text(strip=True) if name_el else title

    hero_data = {
        "slug": slug,
        "name": name,
        "url": url,
        "intro": parse_intro(soup),
        "infobox": parse_infobox(soup),
        "hero_stats": parse_hero_stats(soup),
        "abilities": parse_abilities(soup),
    }

    return hero_data


def write_per_slug_file(output_dir, slug, payload):
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{slug}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Scrape hero data dari Mobile Legends Fandom.")
    parser.add_argument("--heroes", default="hero.json", help="Path ke file hero.json")
    parser.add_argument("--output", default="hero_details.json", help="Path output JSON")
    parser.add_argument("--output-dir", default="hero_by_slug", help="Folder output file per slug")
    parser.add_argument("--no-per-slug", action="store_true", help="Nonaktifkan output per slug")
    parser.add_argument("--only", default="", help="Slug hero spesifik, contoh: miya")
    args = parser.parse_args()

    slugs = load_hero_slugs(args.heroes)

    if args.only:
        only_slug = args.only.strip().lower()
        slugs = [s for s in slugs if s.lower() == only_slug]

    if not slugs:
        raise ValueError("Tidak ada hero yang diproses. Cek hero.json atau --only.")

    results = []
    total = len(slugs)
    for i, slug in enumerate(slugs, start=1):
        print(f"[{i}/{total}] Scraping {slug}...")
        try:
            hero_data = scrape_hero(slug)
            results.append(hero_data)

            if not args.no_per_slug:
                per_slug_path = write_per_slug_file(args.output_dir, slug, hero_data)
                print(f"  -> Per-slug saved: {per_slug_path}")
        except Exception as exc:
            error_payload = {
                "slug": slug,
                "error": str(exc),
            }
            results.append(error_payload)

            if not args.no_per_slug:
                per_slug_path = write_per_slug_file(args.output_dir, slug, error_payload)
                print(f"  -> Per-slug saved: {per_slug_path}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Selesai. Hasil disimpan ke: {args.output}")


if __name__ == "__main__":
    main()
