/* Real HA shell smoke. The Python host owns the isolated config and synthetic auth. */
import { readFile, writeFile, rename, mkdir } from "node:fs/promises";
import { join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { chromium, expect } from "@playwright/test";

const artifacts = process.env.SETLISTFM_LIVE_DIR;
if (!artifacts) throw new Error("Set SETLISTFM_LIVE_DIR to the same directory as the Python smoke host.");
await mkdir(artifacts, { recursive: true });
let host;
for (let attempt = 0; attempt < 120; attempt++) {
  try { host = JSON.parse(await readFile(join(artifacts, "live-host.json"), "utf8")); break; }
  catch (error) {
    if (error.code !== "ENOENT") throw error;
    await delay(500);
  }
}
if (!host || new URL(host.url).hostname !== "127.0.0.1") throw new Error("No loopback HA smoke host became ready.");

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 }, locale: "en-US" });
page.setDefaultTimeout(15000);
const errors = [];
const result = { ok: false, errors };
const pickerName = (preset) => `${host.modern ? "" : "Custom: "}setlist.fm ${preset}`;
page.on("pageerror", (error) => errors.push(error.stack || error.message));
page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
// Branding is unrelated to cards. Keep the real HA shell entirely offline.
await page.route("**/api/brands/**", (route) => route.fulfill({
  contentType: "image/svg+xml",
  body: '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"></svg>',
}));
await page.route(/^https?:\/\/(?!127\.0\.0\.1[:/])/, (route) => {
  const { hostname, pathname } = new URL(route.request().url());
  if (route.request().resourceType() === "image" || /\.(png|svg|jpe?g|webp)$/i.test(pathname)) {
    return route.fulfill({
      contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"></svg>',
    });
  }
  errors.push(`Unexpected external request: ${hostname}${pathname}`);
  return route.abort();
});
await page.addInitScript(({ url, token }) => {
  window.smokeInitialRegistry = customElements;
  window.smokeInitialGet = customElements.get.bind(customElements);
  localStorage.setItem("hassTokens", JSON.stringify({
    hassUrl: url, access_token: token, token_type: "Bearer", expires_in: 1800,
    expires: Date.now() + 1800000, refresh_token: "local-fixture",
  }));
  localStorage.setItem("selectedLanguage", JSON.stringify("en"));
}, { url: host.url.replace(/\/$/, ""), token: host.access_token });

try {
  let reachable = false;
  for (let attempt = 0; attempt < 40; attempt++) {
    try {
      reachable = (await fetch(host.url, { signal: AbortSignal.timeout(500) })).ok;
      if (reachable) break;
    } catch (error) {
      if (attempt === 39) throw error;
    }
    await delay(250);
  }
  if (!reachable) throw new Error("The loopback HA host is not responsive.");
  await page.goto(`${host.url}lovelace/concerts`);
  // HA 2026.9 asks to confirm the fixture's explicit loopback/ephemeral port.
  if (host.modern) await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await page.getByRole("button", { name: "Edit dashboard", exact: true }).click();
  await page.getByRole("button", { name: "Add card", exact: true }).click();
  await page.getByRole("tab", { name: "By card", exact: true }).click();
  if (host.modern) {
    await page.getByRole("button", { name: "Community cards", exact: true }).scrollIntoViewIfNeeded();
  } else {
    await page.getByRole("textbox").fill("setlist.fm");
  }
  for (const preset of ["Complete", "Compact", "Deluxe", "Mobile"]) {
    await expect(page.getByText(pickerName(preset), { exact: true })).toBeVisible();
  }
  await page.screenshot({ path: join(artifacts, "real-ha-community-section.png"), fullPage: true });
  await page.getByRole("textbox").fill("setlist.fm");
  await page.screenshot({ path: join(artifacts, "real-ha-community-search.png"), fullPage: true });
  // HA deliberately overlays each preview, including its title, with this hit target.
  await page.locator("hui-card-picker").locator(".card")
    .filter({ has: page.getByText(pickerName("Complete"), { exact: true }) }).locator(".overlay").click();

  const preview = page.locator("hui-dialog-edit-card setlistfm-complete-card");
  await expect(page.getByLabel("Group by concert visit", { exact: true })).not.toBeChecked();
  await page.getByLabel("Account / concerts entity").selectOption("sensor.sam_renamed_concerts");
  await expect(page.getByLabel("Account / concerts entity").locator("option")).toHaveCount(3);
  await expect(preview.getByRole("status")).toContainText("An empty list does not establish your total attendance.");
  await page.getByLabel("Account / concerts entity").selectOption("sensor.alex_renamed_concerts");
  await expect(preview.getByRole("status")).toContainText(
    "1 invalid record was skipped by the integration"
  );
  await page.getByLabel("Title", { exact: true }).fill("My live music");
  await page.getByLabel("Show", { exact: true }).selectOption("past");
  await page.getByLabel("Maximum concerts per list section (1-50)").fill("3");
  await page.getByLabel("Maximum concerts per list section (1-50)").press("Tab");
  await page.getByLabel("Show listed song counts").uncheck();
  await page.getByLabel("Group by concert visit", { exact: true }).check();
  await expect(preview.locator(".performance-name")).toHaveText(["Recent Fixture Band", "Support Fixture Band"]);
  await expect(preview.locator(".setlist")).toHaveCount(2);
  await expect(preview.getByRole("status").filter({hasText:"Visit grouping is uncertain"})).toBeVisible();
  await page.screenshot({ path: join(artifacts, "real-ha-visual-editor.png"), fullPage: true });
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await expect(page.getByRole("heading", { name: "My live music", exact: true })).toBeVisible();
  await expect(page.locator("setlistfm-complete-card").getByRole("status").filter({hasText:"Attendance data is incomplete"})).toContainText(
    "1 invalid record was skipped by the integration"
  );
  await expect(page.locator("setlistfm-complete-card .performance-name")).toHaveText(["Recent Fixture Band", "Support Fixture Band"]);
  await expect(page.getByText("Future Fixture Band", { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { name: "My live music", exact: true })).toBeVisible();
  await expect(page.locator("setlistfm-complete-card .performance-name")).toHaveText(["Recent Fixture Band", "Support Fixture Band"]);
  await expect(page.locator("setlistfm-complete-card .setlist")).toHaveCount(2);
  await page.screenshot({ path: join(artifacts, "real-ha-saved-card.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: join(artifacts, "real-ha-saved-mobile.png"), fullPage: true });
  expect(errors).toEqual([]);
  result.ok = true;
  console.log(`Real HA ${host.ha_version} card picker, account selection, optional grouped lineup, visual options, save and reload passed.`);
} catch (error) {
  result.failure = error.message;
  try {
    result.registry = await page.evaluate(() => ({
      same: window.smokeInitialRegistry === customElements,
      cards: (window.customCards || []).map(({type}) => ({
        type, initial: !!window.smokeInitialGet(type), current: !!customElements.get(type),
      })),
    }));
    await page.screenshot({ path: join(artifacts, "real-ha-failure.png"), fullPage: true });
    await writeFile(join(artifacts, "real-ha-failure.txt"), await page.locator("body").ariaSnapshot());
  } catch (diagnosticError) {
    result.diagnostic_error = diagnosticError.message;
  }
  process.exitCode = 1;
  console.error(error.message);
} finally {
  await browser.close();
  await writeFile(join(artifacts, "live-result.tmp"), JSON.stringify(result, null, 2));
  await rename(join(artifacts, "live-result.tmp"), join(artifacts, "live-result.json"));
}
