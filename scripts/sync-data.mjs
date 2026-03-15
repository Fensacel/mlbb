import { cp, mkdir, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
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

async function copyAllowedJsonFiles(sourceDir, destinationDir, copiedJsonFiles = new Set()) {
  if (!(await exists(sourceDir))) {
    return copiedJsonFiles;
  }

  const entries = await readdir(sourceDir, { withFileTypes: true });
  for (const entry of entries) {
    if (
      entry.isFile() &&
      entry.name.toLowerCase().endsWith(".json") &&
      ALLOWED_JSON_FILES.has(entry.name) &&
      !copiedJsonFiles.has(entry.name)
    ) {
      const source = path.join(sourceDir, entry.name);
      const destination = path.join(destinationDir, entry.name);
      await cp(source, destination);
      copiedJsonFiles.add(entry.name);
    }
  }

  return copiedJsonFiles;
}

async function copyFirstExistingDir(candidates, destinationDir) {
  for (const sourceDir of candidates) {
    if (await exists(sourceDir)) {
      await cp(sourceDir, destinationDir, { recursive: true });
      return true;
    }
  }

  return false;
}

async function buildHeroesFullJson(destinationDir) {
  const heroListPath = path.join(destinationDir, "hero.json");
  const heroBySlugDir = path.join(destinationDir, "hero_by_slug");
  const outputPath = path.join(destinationDir, "heroes_full.json");

  if (!(await exists(heroListPath)) || !(await exists(heroBySlugDir))) {
    return;
  }

  let heroList = [];
  try {
    const raw = await readFile(heroListPath, "utf8");
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      heroList = parsed;
    }
  } catch {
    heroList = [];
  }

  const merged = [];
  for (const heroName of heroList) {
    const slug = String(heroName || "").trim();
    if (!slug) {
      continue;
    }

    const detailPath = path.join(heroBySlugDir, `${slug}.json`);
    if (await exists(detailPath)) {
      try {
        const detailRaw = await readFile(detailPath, "utf8");
        const detailJson = JSON.parse(detailRaw);
        merged.push(detailJson);
        continue;
      } catch {
        // fall through to placeholder
      }
    }

    merged.push({
      slug,
      name: slug,
      error: `Missing hero detail file for '${slug}'`
    });
  }

  await writeFile(outputPath, `${JSON.stringify(merged, null, 2)}\n`, "utf8");
}

async function syncJsonFiles() {
  await mkdir(outputDir, { recursive: true });

  // Recreate fallback-generated folder to prevent stale hero detail files.
  await rm(path.join(outputDir, "hero_by_slug"), { recursive: true, force: true });

  let copiedJsonFiles = new Set();
  copiedJsonFiles = await copyAllowedJsonFiles(rootDir, outputDir, copiedJsonFiles);
  copiedJsonFiles = await copyAllowedJsonFiles(fallbackDataDir, outputDir, copiedJsonFiles);

  const heroBySlugSource = path.join(rootDir, "hero_by_slug");
  const heroBySlugDestination = path.join(outputDir, "hero_by_slug");
  const fallbackHeroBySlug = path.join(fallbackDataDir, "hero_by_slug");
  await copyFirstExistingDir([heroBySlugSource, fallbackHeroBySlug], heroBySlugDestination);

  if (await exists(webDir)) {
    await cp(webDir, outputDir, { recursive: true });
  }

  await buildHeroesFullJson(outputDir);
}

async function main() {
  await syncJsonFiles();
  console.log("Data assets synced to /public");
}

main().catch((error) => {
  console.error("Failed to sync data assets:", error);
  process.exit(1);
});
