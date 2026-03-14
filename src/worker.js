const JSON_HEADERS = {
  "content-type": "application/json; charset=UTF-8",
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET,OPTIONS",
  "access-control-allow-headers": "content-type",
  "cache-control": "public, max-age=60"
};

const API_TITLE = "MLBB Stats API";
const API_VERSION = "1.1.0";

function normalizeKey(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

function jsonResponse(payload, status = 200, headers = {}) {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: { ...JSON_HEADERS, ...headers }
  });
}

function emptyResponse(status = 204) {
  return new Response(null, {
    status,
    headers: JSON_HEADERS
  });
}

async function fetchAsset(request, env, assetPath) {
  const assetUrl = new URL(request.url);
  assetUrl.pathname = assetPath;
  const response = await env.ASSETS.fetch(new Request(assetUrl.toString(), request));
  return response;
}

async function fetchAssetJson(request, env, assetPath) {
  const response = await fetchAsset(request, env, assetPath);
  if (!response.ok) {
    return null;
  }

  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function getHeroesList(request, env) {
  const heroes = await fetchAssetJson(request, env, "/hero.json");
  return Array.isArray(heroes) ? heroes : [];
}

function buildOpenApiSchema(baseUrl) {
  return {
    openapi: "3.0.3",
    info: {
      title: API_TITLE,
      version: API_VERSION,
      description: "Public API for hero and item stats generated from scraper datasets."
    },
    servers: [{ url: baseUrl }],
    paths: {
      "/api/health": {
        get: {
          summary: "Health check",
          responses: { "200": { description: "Service is healthy" } }
        }
      },
      "/api/heroes": {
        get: {
          summary: "List heroes",
          parameters: [
            { name: "q", in: "query", schema: { type: "string" } },
            { name: "limit", in: "query", schema: { type: "integer", minimum: 1 } }
          ],
          responses: { "200": { description: "Hero list" } }
        }
      },
      "/api/heroes/{slug}": {
        get: {
          summary: "Get hero by slug",
          parameters: [
            { name: "slug", in: "path", required: true, schema: { type: "string" } }
          ],
          responses: {
            "200": { description: "Hero detail" },
            "404": { description: "Hero not found" }
          }
        }
      },
      "/api/items": {
        get: {
          summary: "List items",
          parameters: [
            { name: "q", in: "query", schema: { type: "string" } },
            { name: "limit", in: "query", schema: { type: "integer", minimum: 1 } }
          ],
          responses: { "200": { description: "Item list" } }
        }
      },
      "/api/items/{slug}": {
        get: {
          summary: "Get item by slug",
          parameters: [
            { name: "slug", in: "path", required: true, schema: { type: "string" } }
          ],
          responses: {
            "200": { description: "Item detail" },
            "404": { description: "Item not found" }
          }
        }
      }
    }
  };
}

async function handleApiRoutes(request, env) {
  const method = request.method.toUpperCase();
  if (method === "OPTIONS") {
    return emptyResponse();
  }

  if (method !== "GET") {
    return jsonResponse({ error: "Method not allowed" }, 405);
  }

  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";

  if (path === "/api" || path === "/api/") {
    return jsonResponse({
      name: API_TITLE,
      version: API_VERSION,
      date: "2026-03-15",
      endpoints: [
        "GET /api/schema",
        "GET /api/health",
        "GET /api/heroes",
        "GET /api/heroes/:slug",
        "GET /api/items",
        "GET /api/items/:slug"
      ]
    });
  }

  if (path === "/api/schema") {
    const schema = buildOpenApiSchema(url.origin);
    return jsonResponse(schema);
  }

  if (path === "/api/health") {
    return jsonResponse({ status: "ok", timestamp: new Date().toISOString() });
  }

  if (path === "/api/heroes") {
    const heroes = await getHeroesList(request, env);
    const q = (url.searchParams.get("q") || "").trim().toLowerCase();
    const limitRaw = Number.parseInt(url.searchParams.get("limit") || "0", 10);

    let filtered = heroes;
    if (q) {
      filtered = heroes.filter((name) => String(name).toLowerCase().includes(q));
    }

    if (Number.isFinite(limitRaw) && limitRaw > 0) {
      filtered = filtered.slice(0, limitRaw);
    }

    return jsonResponse({ count: filtered.length, data: filtered });
  }

  if (path.startsWith("/api/heroes/")) {
    const slug = decodeURIComponent(path.replace("/api/heroes/", "")).trim();
    if (!slug) {
      return jsonResponse({ error: "Hero slug is required" }, 400);
    }

    const heroes = await getHeroesList(request, env);
    const lookup = normalizeKey(slug);
    const canonicalName = heroes.find((name) => normalizeKey(name) === lookup) || slug;
    const details = await fetchAssetJson(request, env, `/hero_by_slug/${canonicalName}.json`);

    if (!details) {
      return jsonResponse({ error: `Hero '${slug}' not found` }, 404);
    }

    return jsonResponse(details);
  }

  if (path === "/api/items") {
    const items = await fetchAssetJson(request, env, "/items_data.json");
    const normalizedItems = Array.isArray(items) ? items : [];

    const q = (url.searchParams.get("q") || "").trim().toLowerCase();
    const limitRaw = Number.parseInt(url.searchParams.get("limit") || "0", 10);

    let filtered = normalizedItems;
    if (q) {
      filtered = normalizedItems.filter((item) => {
        const name = String(item?.name || "").toLowerCase();
        const slug = String(item?.slug || "").toLowerCase();
        return name.includes(q) || slug.includes(q);
      });
    }

    if (Number.isFinite(limitRaw) && limitRaw > 0) {
      filtered = filtered.slice(0, limitRaw);
    }

    return jsonResponse({ count: filtered.length, data: filtered });
  }

  if (path.startsWith("/api/items/")) {
    const slug = decodeURIComponent(path.replace("/api/items/", "")).trim().toLowerCase();
    if (!slug) {
      return jsonResponse({ error: "Item slug is required" }, 400);
    }

    const items = await fetchAssetJson(request, env, "/items_data.json");
    if (!Array.isArray(items)) {
      return jsonResponse({ error: "Item dataset is not available" }, 404);
    }

    const item = items.find((entry) => String(entry?.slug || "").toLowerCase() === slug);
    if (!item) {
      return jsonResponse({ error: `Item '${slug}' not found` }, 404);
    }

    return jsonResponse(item);
  }

  return null;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api")) {
      const apiResponse = await handleApiRoutes(request, env);
      if (apiResponse) {
        return apiResponse;
      }
    }

    return env.ASSETS.fetch(request);
  }
};
