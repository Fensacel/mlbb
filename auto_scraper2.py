import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime

import requests

from scraper2 import API_URL, HEADERS, load_hero_slugs, resolve_page_title


LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".auto_scraper2.lock")


def file_hash(path):
    """Return SHA256 hash of file content; None if file does not exist."""
    if not os.path.exists(path):
        return None

    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def load_state(state_file):
    if not os.path.exists(state_file):
        return {}

    try:
        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass

    return {}


def save_state(state_file, state):
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def run_scraper2(
    python_executable,
    scraper_script,
    heroes_file,
    output_file,
    output_dir,
    no_per_slug,
    only_slug,
):
    cmd = [
        python_executable,
        scraper_script,
        "--heroes",
        heroes_file,
        "--output",
        output_file,
        "--output-dir",
        output_dir,
    ]

    if no_per_slug:
        cmd.append("--no-per-slug")

    if only_slug:
        cmd.extend(["--only", only_slug])

    print(f"[{datetime.now().isoformat(timespec='seconds')}] Menjalankan scraper2...")
    result = subprocess.run(cmd, check=False)
    return result.returncode == 0


def get_latest_revision_id(page_title):
    """Return latest revision id for a wiki page title, or None when unavailable."""
    params = {
        "action": "query",
        "format": "json",
        "prop": "revisions",
        "rvprop": "ids",
        "rvlimit": 1,
        "titles": page_title,
    }

    try:
        resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=25)
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return None

    pages = payload.get("query", {}).get("pages", {})
    for page in pages.values():
        revisions = page.get("revisions", [])
        if revisions:
            return revisions[0].get("revid")

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Automation: cek update tiap hero dan auto scrape hero yang berubah."
    )
    parser.add_argument("--heroes", default="hero.json", help="File sumber daftar hero.")
    parser.add_argument("--output", default="hero_details.json", help="File output utama.")
    parser.add_argument("--output-dir", default="hero_by_slug", help="Folder output per slug.")
    parser.add_argument("--no-per-slug", action="store_true", help="Nonaktifkan output per slug.")
    parser.add_argument("--only", default="", help="Scrape slug hero tertentu saja.")
    parser.add_argument("--state", default=".scrape2_state.json", help="File state internal automation.")
    parser.add_argument("--interval", type=int, default=300, help="Interval cek (detik).")
    parser.add_argument("--python", default="python", help="Path executable python.")
    parser.add_argument("--scraper", default="scraper2.py", help="Path script scraper2.")
    parser.add_argument(
        "--run-on-start",
        action="store_true",
        help="Paksa scrape semua hero saat startup, lalu lanjut monitor.",
    )
    args = parser.parse_args()

    lock_path = LOCK_FILE
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(lock_fd, str(os.getpid()).encode("utf-8"))
        os.close(lock_fd)
    except FileExistsError:
        print("auto_scraper2 sudah berjalan. Keluar untuk mencegah duplikasi instance.")
        return

    state = load_state(args.state)
    revisions = state.get("revisions", {}) if isinstance(state.get("revisions"), dict) else {}
    titles = state.get("titles", {}) if isinstance(state.get("titles"), dict) else {}

    print("Automation scraper2 aktif (cek per-hero). Tekan Ctrl+C untuk stop.")

    try:
        while True:
            slugs = load_hero_slugs(args.heroes)
            if args.only:
                only_slug = args.only.strip().lower()
                slugs = [s for s in slugs if s.lower() == only_slug]

            if not slugs:
                print("Tidak ada hero untuk dicek. Cek file heroes atau argumen --only.")
                time.sleep(max(args.interval, 5))
                continue

            changed_count = 0
            checked_count = 0

            for slug in slugs:
                checked_count += 1

                title = titles.get(slug)
                if not title:
                    title = resolve_page_title(slug)
                    if title:
                        titles[slug] = title

                if not title:
                    print(f"- [{slug}] Lewati: title wiki tidak ditemukan.")
                    continue

                latest_revid = get_latest_revision_id(title)
                if latest_revid is None:
                    print(f"- [{slug}] Lewati: gagal cek revision id.")
                    continue

                is_startup_force = args.run_on_start and not state.get("startup_done")
                previous_revid = revisions.get(slug)

                if not is_startup_force and previous_revid == latest_revid:
                    print(f"- [{slug}] Tidak ada update, lanjut hero berikutnya.")
                    continue

                print(f"- [{slug}] Update terdeteksi, scraping...")
                success = run_scraper2(
                    python_executable=args.python,
                    scraper_script=args.scraper,
                    heroes_file=args.heroes,
                    output_file=args.output,
                    output_dir=args.output_dir,
                    no_per_slug=args.no_per_slug,
                    only_slug=slug,
                )

                if success:
                    revisions[slug] = latest_revid
                    changed_count += 1
                    state["last_success"] = datetime.now().isoformat(timespec="seconds")
                    print(f"- [{slug}] Selesai update.")
                else:
                    print(f"- [{slug}] Gagal scrape. Akan dicoba lagi di siklus berikutnya.")

            state["revisions"] = revisions
            state["titles"] = titles
            state["startup_done"] = True
            state["last_heroes_hash"] = file_hash(args.heroes)
            save_state(args.state, state)

            if changed_count == 0:
                print(
                    f"[{datetime.now().isoformat(timespec='seconds')}] Tidak ada hero yang berubah "
                    f"({checked_count} dicek)."
                )
            else:
                print(
                    f"[{datetime.now().isoformat(timespec='seconds')}] {changed_count} hero diperbarui "
                    f"dari {checked_count} hero yang dicek."
                )

            time.sleep(max(args.interval, 5))
    except KeyboardInterrupt:
        print("Automation scraper2 dihentikan oleh user.")
    finally:
        if os.path.exists(lock_path):
            try:
                os.remove(lock_path)
            except OSError:
                pass


if __name__ == "__main__":
    main()
