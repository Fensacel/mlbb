import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime


LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".auto_scraper1.lock")


def file_hash(path):
    """Return SHA256 hash of a file content; None if file does not exist."""
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


def run_scraper(python_executable, scraper_script, input_file, output_file, limit):
    cmd = [python_executable, scraper_script, "--input", input_file, "--output", output_file]
    if limit and limit > 0:
        cmd.extend(["--limit", str(limit)])

    print(f"[{datetime.now().isoformat(timespec='seconds')}] Menjalankan scraper...")
    result = subprocess.run(cmd, check=False)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Automation: monitor perubahan file input dan auto scrape saat ada update."
    )
    parser.add_argument("--input", default="items_v2.json", help="File sumber item.")
    parser.add_argument("--output", default="items_data.json", help="File hasil scrape.")
    parser.add_argument("--state", default=".scrape_state.json", help="File state internal automation.")
    parser.add_argument("--interval", type=int, default=300, help="Interval cek (detik).")
    parser.add_argument("--python", default="python", help="Path executable python.")
    parser.add_argument("--scraper", default="scraper.py", help="Path script scraper utama.")
    parser.add_argument("--limit", type=int, default=0, help="Limit item saat auto scrape (0 = semua).")
    parser.add_argument(
        "--run-on-start",
        action="store_true",
        help="Jalankan scrape sekali saat startup, lalu lanjut monitor.",
    )
    args = parser.parse_args()

    lock_path = LOCK_FILE
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(lock_fd, str(os.getpid()).encode("utf-8"))
        os.close(lock_fd)
    except FileExistsError:
        print("auto_scraper sudah berjalan. Keluar untuk mencegah duplikasi instance.")
        return

    state = load_state(args.state)
    print("Automation scraper aktif. Tekan Ctrl+C untuk stop.")

    if args.run_on_start:
        success = run_scraper(
            python_executable=args.python,
            scraper_script=args.scraper,
            input_file=args.input,
            output_file=args.output,
            limit=args.limit,
        )
        if success:
            state["last_input_hash"] = file_hash(args.input)
            state["last_success"] = datetime.now().isoformat(timespec="seconds")
            save_state(args.state, state)

    try:
        while True:
            current_hash = file_hash(args.input)
            previous_hash = state.get("last_input_hash")

            output_missing = not os.path.exists(args.output)
            has_changed = current_hash is not None and current_hash != previous_hash

            if output_missing or has_changed:
                reason = "output belum ada" if output_missing else "input berubah"
                print(f"[{datetime.now().isoformat(timespec='seconds')}] Trigger scrape ({reason}).")

                success = run_scraper(
                    python_executable=args.python,
                    scraper_script=args.scraper,
                    input_file=args.input,
                    output_file=args.output,
                    limit=args.limit,
                )

                if success:
                    state["last_input_hash"] = current_hash
                    state["last_success"] = datetime.now().isoformat(timespec="seconds")
                    save_state(args.state, state)
                    print("Scrape selesai dan state diperbarui.")
                else:
                    print("Scrape gagal. Akan dicoba lagi di interval berikutnya.")
            else:
                print(f"[{datetime.now().isoformat(timespec='seconds')}] Tidak ada update.")

            time.sleep(max(args.interval, 5))
    except KeyboardInterrupt:
        print("Automation dihentikan oleh user.")
    finally:
        if os.path.exists(lock_path):
            try:
                os.remove(lock_path)
            except OSError:
                pass


if __name__ == "__main__":
    main()
