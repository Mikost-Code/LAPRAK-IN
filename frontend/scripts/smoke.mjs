// Browser smoke test against a running backend (LAPRAK_DEV_LOGIN=1) that serves frontend/dist.
// Usage: node scripts/smoke.mjs [baseUrl] [outDir]
import fs from "node:fs";
import path from "node:path";
import puppeteer from "puppeteer-core";

const base = process.argv[2] ?? "http://127.0.0.1:8000";
const out = process.argv[3] ?? path.resolve("../.local/web-qa");
fs.mkdirSync(out, { recursive: true });
const chrome = ["C:/Program Files/Google/Chrome/Application/chrome.exe", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "/usr/bin/chromium", "/usr/bin/google-chrome"].find((p) => fs.existsSync(p));
if (!chrome) throw new Error("No Chromium executable found.");

const browser = await puppeteer.launch({ executablePath: chrome, headless: true, args: ["--no-sandbox"] });
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 820 });
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("console", (m) => m.type() === "error" && !m.text().includes("401") && errors.push("console: " + m.text()));
page.on("response", (r) => r.status() >= 400 && !r.url().includes("/api/auth/me") && errors.push(`http ${r.status()} ${r.url()}`));

process.on("unhandledRejection", async (e) => { try { await page.screenshot({ path: path.join(out, "error.png"), fullPage: true }); console.error("page text:", (await page.evaluate(() => document.body.innerText)).slice(0, 1500)); } catch {} console.error(e); process.exit(1); });
const shot = (name) => page.screenshot({ path: path.join(out, name + ".png"), fullPage: true });
const click = async (text, tag = "button") => {
  const handle = await page.waitForSelector(`${tag}::-p-text(${text})`, { timeout: 10000 });
  await handle.click();
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await page.goto(base + "/login", { waitUntil: "networkidle0" });
await shot("01-login");
await click("Masuk pengembang");
await page.waitForSelector("h1::-p-text(Proyek laporan)");
await shot("02-home");

await click("Proyek baru");
await page.type(".modal input", "Laporan Uji Web");
await click("Lanjut");
await page.waitForSelector("h1::-p-text(Persiapan)");
await page.type('input[value=""]', "Mahasiswa Uji");
await sleep(1200);
await shot("03-setup");

await click("Template", "a");
await page.waitForSelector(".dropzone");
const zipPath = path.resolve(out, "template.zip");
if (!fs.existsSync(zipPath)) {
  // Build the ZIP from the repo template with Node only.
  const { execSync } = await import("node:child_process");
  execSync(`powershell -NoProfile -Command "Compress-Archive -Force -Path '${path.resolve("../template/*")}' -DestinationPath '${zipPath}'"`);
}
const [chooser] = await Promise.all([page.waitForFileChooser(), page.click(".dropzone")]);
await chooser.accept([zipPath]);
await page.waitForSelector("h2::-p-text(ITERA)", { timeout: 15000 });
await shot("04-template");

await click("Dokumentasi", "a");
await click("Tambah langkah");
await page.waitForSelector(".step-item.selected");
await page.click(".docs-layout .card:nth-child(2) input", { clickCount: 3 });
await page.type(".docs-layout .card:nth-child(2) input", "Konfigurasi awal");
const png = path.join(out, "sample.png");
fs.writeFileSync(png, Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", "base64"));
const [chooser2] = await Promise.all([page.waitForFileChooser(), page.click(".docs-layout .card:nth-child(2) .dropzone")]);
await chooser2.accept([png]);
await page.waitForSelector(".thumb img");
await page.type("textarea.tall", "Langkah pertama dilakukan dengan baik.");
await sleep(1500);
await shot("05-docs");

await click("Periksa", "a");
await page.waitForSelector(".blocker");
await shot("06-review");
await click("PDF", "a");
await page.waitForSelector("h1::-p-text(PDF)");
await page.waitForSelector(".tag.good::-p-text(Compiler)", { timeout: 60000 });
await click("Bangun pratinjau");
await page.waitForSelector("iframe.pdf-frame", { timeout: 120000 });
await sleep(1500);
await shot("07-pdf");

await browser.close();
if (errors.length) {
  console.error("Smoke finished with browser errors:\n" + errors.join("\n"));
  process.exit(1);
}
console.log("Smoke OK. Screenshots in " + out);
