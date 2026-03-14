# Molebuild Scraper API (Cloudflare Worker)

Project ini mengubah output scraper JSON menjadi API yang bisa di-host di Cloudflare Worker.

Landing page docs/test ada di root URL (`/`) dengan UI interaktif untuk ngetes endpoint.

## Endpoint API

- `GET /api`
- `GET /api/schema`
- `GET /api/health`
- `GET /api/heroes?q=<keyword>&limit=<n>`
- `GET /api/heroes/:slug`
- `GET /api/items?q=<keyword>&limit=<n>`
- `GET /api/items/:slug`

Contoh:

- `GET /api/heroes?q=miya`
- `GET /api/heroes/miya`
- `GET /api/items?q=oracle`
- `GET /api/items/oracle`

## Landing Page

- `GET /` untuk docs + API tester
- Klik endpoint atau isi path endpoint, lalu `Run Request`
- Bisa copy hasil JSON langsung dari UI

## Struktur Data yang Dipakai

Worker membaca file data dari folder `public`:

- `public/hero.json`
- `public/items_data.json`
- `public/hero_by_slug/*.json`

Folder `public` tidak di-edit manual. Folder ini di-generate dari root project oleh script sync.

Urutan sumber data saat sync:

1. Data utama dari root project (hasil scraper)
2. Fallback dari folder `data` jika file utama tidak ada
3. Asset landing page dari folder `web`

## Cara Menjalankan Lokal

1. Install dependency:
   - `npm install`
2. Sinkronkan data JSON ke assets:
   - `npm run sync:data`
3. Jalankan lokal:
   - `npm run dev`

Jika file JSON scraper belum ada, endpoint tetap hidup tapi data akan kosong / not found.
Secara default, project menyediakan sample data fallback supaya API langsung bisa dites.

## Deploy ke Cloudflare

1. Login Wrangler:
   - `npx wrangler login`
2. Deploy:
   - `npm run deploy`

Setelah deploy, API bisa diakses lewat domain Worker Cloudflare.

## Setup GitHub Actions

Workflow file yang dipakai (3 workflow):

- `.github/workflows/scrape-items.yml`
   - Jalan terjadwal untuk update `items_data.json`.
   - Menjalankan `scraper.py`.
   - Commit otomatis bila ada perubahan item.

- `.github/workflows/scrape-heroes.yml`
   - Jalan terjadwal untuk update `hero_details.json` dan folder `hero_by_slug`.
   - Menjalankan `scraper2.py`.
   - Commit otomatis bila ada perubahan hero.

- `.github/workflows/deploy-worker.yml`
   - Jalan saat ada push ke branch `main`/`master` pada file relevan API/data.
   - Menjalankan `npm run sync:data` lalu `wrangler deploy`.

Secrets yang wajib di GitHub Repository Settings -> Secrets and variables -> Actions:

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

Minimal permission token Cloudflare:

- `Account` -> `Cloudflare Workers:Edit`
- `Zone` tidak wajib kalau hanya deploy Worker tanpa custom route.

Langkah aktifkan:

1. Push file workflow ke branch utama.
2. Tambahkan 2 secrets di atas.
3. Jalankan manual `Scrape Items Data` lalu `Scrape Heroes Data` sekali dari tab Actions untuk test awal.
4. Cek apakah commit data muncul otomatis.
5. Pastikan `Deploy Worker` sukses setelah commit data tersebut.

## Tentang request `/api/wp-login-config`

Request ini biasanya dari bot scanner internet yang nyari endpoint WordPress, bukan dari aplikasi kamu.
Karena API kamu publik, path acak seperti ini normal terlihat di log dan akan dibalas `404`.

Jika ingin mengurangi noise:

- Tambah WAF rule di Cloudflare untuk challenge/block path yang mengandung `wp-login`.
- Batasi akses berdasarkan negara/ASN bila target user kamu spesifik.
- Simpan/monitor hanya path penting (`/api/heroes`, `/api/items`, dll.) di observability tooling.

## Catatan Penting

- Setiap ada update file JSON hasil scraping, jalankan lagi:
  - `npm run sync:data`
- Saat deploy, script `deploy` otomatis menjalankan sync sebelum upload.
