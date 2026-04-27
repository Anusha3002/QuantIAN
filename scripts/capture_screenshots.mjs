#!/usr/bin/env node
// Captures a PNG per dashboard tab. Expects the local stack + the
// React dashboard to be running:
//   mosquitto -d -p 1883
//   python scripts/run_local_stack.py --with-iot-bridge
//   cd web_dashboard && npm run dev
// then in a separate terminal:
//   npx puppeteer-core --version >/dev/null  # ensure installed
//   node scripts/capture_screenshots.mjs

import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = resolve(__dirname, "..", "docs", "screenshots");
const BASE = process.env.DASHBOARD_URL ?? "http://127.0.0.1:5174";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "peers", label: "Peers" },
  { id: "alerts", label: "Alerts" },
  { id: "risk", label: "Risk" },
  { id: "ledger", label: "Ledger" },
  { id: "iot", label: "IoT" },
];

const VIEWPORT = { width: 1440, height: 900, deviceScaleFactor: 1 };
const FULL_PAGE_TABS = new Set(["ledger", "alerts"]);

async function main() {
  await mkdir(OUT_DIR, { recursive: true });

  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport(VIEWPORT);
    await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "dark" }]);

    console.log(`→ loading ${BASE}`);
    await page.goto(BASE, { waitUntil: "networkidle2", timeout: 20000 });

    // wait for KPI tiles to render
    await page.waitForSelector("nav button", { timeout: 10000 });
    await sleep(1200);

    for (const tab of TABS) {
      console.log(`  clicking "${tab.label}"`);
      await page.evaluate((label) => {
        const buttons = Array.from(document.querySelectorAll("nav button"));
        const target = buttons.find((b) => b.textContent?.trim() === label);
        if (target instanceof HTMLElement) target.click();
      }, tab.label);

      await sleep(1500); // let charts finish animating / polling finish

      const out = resolve(OUT_DIR, `${tab.id}.png`);
      await page.screenshot({ path: out, fullPage: FULL_PAGE_TABS.has(tab.id) });
      console.log(`  ✓ ${tab.id}.png`);
    }
  } finally {
    await browser.close();
  }

  console.log(`\nall screenshots written to ${OUT_DIR}`);
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
