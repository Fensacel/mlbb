# MLBB Stats API

README ini fokus ke cara pakai API.

Base URL contoh:
https://example.workers.dev

## Endpoint Yang Dipakai

- GET /api
- GET /api/schema
- GET /api/health
- GET /api/heroes
- GET /api/heroes?q=miya
- GET /api/hero-details/:slug
- GET /api/hero-details/:slug/abilities
- GET /api/items
- GET /api/items?q=oracle

Catatan:
- Endpoint items detail per slug sudah tidak ada.
- Detail dan abilities hero diakses lewat hero-details.

## Bentuk Response Singkat

GET /api/heroes atau /api/items:

```json
{
  "count": 132,
  "data": ["Miya", "Balmond"]
}
```

GET /api/hero-details/miya:

```json
{
  "slug": "Miya",
  "name": "Miya",
  "hero_stats": {},
  "abilities": []
}
```

GET /api/hero-details/miya/abilities:

```json
{
  "slug": "Miya",
  "name": "Miya",
  "abilities": []
}
```

## Cara Pakai di Frontend

```html
<script>
  async function getHeroes() {
    const res = await fetch("https://example.workers.dev/api/heroes");
    const json = await res.json();
    return json.data;
  }

  async function getHeroDetail(slug) {
    const res = await fetch(`https://example.workers.dev/api/hero-details/${slug}`);
    if (!res.ok) throw new Error("Hero tidak ditemukan");
    return res.json();
  }

  async function getHeroAbilities(slug) {
    const res = await fetch(`https://example.workers.dev/api/hero-details/${slug}/abilities`);
    if (!res.ok) throw new Error("Abilities tidak ditemukan");
    return res.json();
  }
</script>
```

## Cara Pakai di Backend (Node.js)

```js
const baseUrl = "https://example.workers.dev";

async function getItems(keyword = "") {
  const url = keyword
    ? `${baseUrl}/api/items?q=${encodeURIComponent(keyword)}`
    : `${baseUrl}/api/items`;

  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}
```

## Cara Tes Cepat (curl)

```bash
curl https://example.workers.dev/api/heroes
curl https://example.workers.dev/api/hero-details/miya
curl https://example.workers.dev/api/hero-details/miya/abilities
curl "https://example.workers.dev/api/items?q=oracle"
```

## Integrasi Cepat

- List page hero: pakai GET /api/heroes
- Hero detail page: pakai GET /api/hero-details/:slug
- Hero skills tab: pakai GET /api/hero-details/:slug/abilities
- List page items: pakai GET /api/items
- Search: tambah query q
