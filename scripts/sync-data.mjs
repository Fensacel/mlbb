import { cp, mkdir, readdir, rm, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, "..");
const outputDir = path.join(rootDir, "public");
const webDir = path.join(rootDir, "web");
const fallbackDataDir = path.join(rootDir, "data");
const ALLOWED_JSON_FILES = new Set([
  "hero.json",
  "hero_details.json",
  "hero_5.json",
  "hero_5_details.json",
  "hero_miya.json",
  "hero_miya_list.json",
  "items_data.json",
  "items_v2.json",
  "full_items_data.json"
]);

async function exists(targetPath) {
  try {
    await stat(targetPath);
    return true;
  } catch {
    return false;
  }
}

async function syncJsonFiles() {
  await mkdir(outputDir, { recursive: true });

  // Recreate fallback-generated folder to prevent stale hero detail files.
  await rm(path.join(outputDir, "hero_by_slug"), { recursive: true, force: true });

  const entries = await readdir(rootDir, { withFileTypes: true });
  const copiedJsonFiles = new Set();
  for (const entry of entries) {
    if (
      entry.isFile() &&
      entry.name.toLowerCase().endsWith(".json") &&
      ALLOWED_JSON_FILES.has(entry.name)
    ) {
      const source = path.join(rootDir, entry.name);
      const destination = path.join(outputDir, entry.name);
      await cp(source, destination);
      copiedJsonFiles.add(entry.name);
    }
  }

  if (await exists(fallbackDataDir)) {
    const fallbackEntries = await readdir(fallbackDataDir, { withFileTypes: true });
    for (const entry of fallbackEntries) {
      if (
        entry.isFile() &&
        entry.name.toLowerCase().endsWith(".json") &&
        ALLOWED_JSON_FILES.has(entry.name) &&
        !copiedJsonFiles.has(entry.name)
      ) {
        const source = path.join(fallbackDataDir, entry.name);
        const destination = path.join(outputDir, entry.name);
        await cp(source, destination);
      }
    }
  }

  const heroBySlugSource = path.join(rootDir, "hero_by_slug");
  const heroBySlugDestination = path.join(outputDir, "hero_by_slug");
  if (await exists(heroBySlugSource)) {
    await cp(heroBySlugSource, heroBySlugDestination, { recursive: true });
  } else {
    const fallbackHeroBySlug = path.join(fallbackDataDir, "hero_by_slug");
    if (await exists(fallbackHeroBySlug)) {
      await cp(fallbackHeroBySlug, heroBySlugDestination, { recursive: true });
    }
  }

  if (await exists(webDir)) {
    await cp(webDir, outputDir, { recursive: true });
  }
}

async function main() {
  await syncJsonFiles();
  console.log("Data assets synced to /public");
}

main().catch((error) => {
  console.error("Failed to sync data assets:", error);
  process.exit(1);
});
