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
- GET /api/heroes-full
- GET /api/items
- GET /api/items?q=oracle

Catatan:
- Endpoint items detail per slug sudah tidak ada.

## Bentuk Response Singkat

GET /api/heroes atau /api/items:

```json
{
  "count": 132,
  "data": ["Miya", "Balmond"]
}
```

GET /api/heroes-full:

```json
{
  "count": 132,
  "data": [
    {
      "slug": "Miya",
      "name": "Miya",
      "abilities": []
    }
  ]
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

  async function getHeroesFull() {
    const res = await fetch("https://example.workers.dev/api/heroes-full");
    const json = await res.json();
    return json.data;
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
curl https://example.workers.dev/api/heroes-full
curl "https://example.workers.dev/api/items?q=oracle"
```

## Integrasi Cepat

- List page hero: pakai GET /api/heroes
- Semua detail 132 hero dalam 1 call: pakai GET /api/heroes-full
- List page items: pakai GET /api/items
- Search: tambah query q
