import json
import time
import re
import argparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def normalize_stat_text(text):
    """Normalize stat strings so output is consistent with items_data.json."""
    if not text:
        return ""

    cleaned = " ".join(text.split())
    cleaned = cleaned.replace("Harga: ", "")
    cleaned = re.sub(r"\bgold\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.split())

    # Convert decimal multiplier style to percent (e.g. *0.05 -> +5%)
    cleaned = re.sub(r'\*([0-9.]+)', lambda m: f"+{int(float(m.group(1)) * 100)}%", cleaned)

    return cleaned.strip()


def deduplicate_preserve_order(values):
    """Remove duplicates while preserving original order."""
    out = []
    seen = set()
    for val in values:
        key = val.lower()
        if key not in seen:
            seen.add(key)
            out.append(val)
    return out

def load_items_from_json(filepath):
    """
    Fungsi untuk membaca data item dari file input JSON.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: File '{filepath}' tidak ditemukan.")
        return []
    except json.JSONDecodeError:
        print(f"Error: Format file '{filepath}' bukan JSON yang valid.")
        return []

def scrape_item_data_playwright(page, slug):
    """
    Fungsi untuk mengambil data statistik (stats) dan 
    top heroes dari halaman item berdasarkan slug.
    """
    url = f"https://molebuild.com/items/{slug}"
    
    try:
        # Menunggu hingga halaman network stabil (Client side rendering kelar)
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
    except PlaywrightTimeoutError:
        print(f"  -> [Error] Timeout mengakses URL {url}")
        return None
    except Exception as e:
        print(f"  -> [Error] Gagal mengakses URL {url} | Detail: {e}")
        return None

    # Biarkan render JS berjalan sebentar sebelum parsing DOM
    page.wait_for_timeout(2000)

    # Inisialisasi wadah penampung
    scraped_data = {
        'stats': []
    }

    # Ekstraksi 1: Karakteristik / Stats Item
    
    # 1. Price
    price_locator = page.locator('.text-xl.font-bold.text-amber-500')
    if price_locator.count() > 0:
        # Biasanya teks seperti "2010 gold"
        price_text = normalize_stat_text(price_locator.nth(0).inner_text())
        if price_text:
            scraped_data['stats'].append(price_text)
        

    # 2. Stats Utama (+40 physical defense, dll)
    stats_locators = page.locator('.flex.items-center.gap-2.text-sm, .flex.items-center.gap-1\\.5')
    for i in range(stats_locators.count()):
        stat_text = normalize_stat_text(stats_locators.nth(i).inner_text())
        if stat_text:
            if 'total penggunaan' in stat_text.lower():
                parts = stat_text.split('•')
                if parts:
                    stat_text = parts[0].strip()
            if stat_text:
                scraped_data['stats'].append(stat_text)
            
    # 3. Deskripsi Pasif
    # Mencari header "Pasif" lalu mengambil deskripsinya
    passive_header = page.locator('h3:has-text("Pasif")')
    if passive_header.count() > 0:
        # Biasanya deskripsi pasif ada di div terdekat setelahnya
        passive_desc = passive_header.locator('~ div.text-sm').nth(0)
        if passive_desc.count() > 0:
            passive_text = normalize_stat_text(passive_desc.inner_text())
            if passive_text:
                if not passive_text.lower().startswith("pasif:"):
                    passive_text = f"Pasif: {passive_text}"
                scraped_data['stats'].append(passive_text)
    else:
        # Fallback menggunakan .font-medium jika tidak pakai urutan h3
        passive_locators = page.locator('.text-sm.leading-relaxed.text-muted-foreground')
        for i in range(passive_locators.count()):
            passive_text = normalize_stat_text(passive_locators.nth(i).inner_text())
            if passive_text:
                if not passive_text.lower().startswith("pasif:"):
                    passive_text = f"Pasif: {passive_text}"
                scraped_data['stats'].append(passive_text)

    scraped_data['stats'] = deduplicate_preserve_order(scraped_data['stats'])


    return scraped_data

def main(input_file="items_v2.json", output_file="items_data.json", limit=None):
    print("Membaca data item...")
    items = load_items_from_json(input_file)
    
    if not items:
        print("Data item kosong atau terjadi error. Program dihentikan.")
        return

    if limit is not None and limit > 0:
        items = items[:limit]
        print(f"Berhasil memuat {len(items)} item (mode limit). Memulai proses scraping dengan Playwright...\n")
    else:
        print(f"Berhasil memuat {len(items)} item. Memulai proses scraping dengan Playwright...\n")
    processed_items = []

    with sync_playwright() as p:
        # Buka virtual browser headless
        browser = p.chromium.launch(headless=True)
        # Menambahkan User-Agent nyata untuk terhindar dari pemblokiran
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Looping semua item
        for index, item in enumerate(items, start=1):
            slug = item.get('slug')
            name = item.get('name', 'Unknown Item')
            
            if not slug:
                print(f"[{index}/{len(items)}] Melewati '{name}' karena tidak memiliki key 'slug'.")
                processed_items.append(item)
                continue
                
            print(f"[{index}/{len(items)}] Scraping data: {name}...")
            
            extracted_data = scrape_item_data_playwright(page, slug)

            output_item = {
                'name': item.get('name', ''),
                'slug': item.get('slug', ''),
                'image_url': item.get('image_url', ''),
                'stats': extracted_data.get('stats', []) if extracted_data else []
            }

            processed_items.append(output_item)
            
            time.sleep(1) # Jeda waktu

        browser.close()

    try:
        with open(output_file, 'w', encoding='utf-8') as file:
            json.dump(processed_items, file, indent=4, ensure_ascii=False)
        print(f"\n[SUKSES] Seluruh data berhasil digabungkan dan disimpan pada: '{output_file}'")
    except IOError as e:
        print(f"\n[ERROR] Terdapat kendala saat menyimpan ke file output: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape item data dari molebuild.")
    parser.add_argument("--input", default="items_v2.json", help="File input JSON item.")
    parser.add_argument("--output", default="items_data.json", help="File output JSON hasil scrape.")
    parser.add_argument("--limit", type=int, default=0, help="Batasi jumlah item untuk test (0 = semua).")
    args = parser.parse_args()

    run_limit = args.limit if args.limit and args.limit > 0 else None
    main(input_file=args.input, output_file=args.output, limit=run_limit)
