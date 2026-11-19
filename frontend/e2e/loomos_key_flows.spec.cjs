/**
 * LOOMOS Phase 4 Focused Playwright E2E Suite — 4 Key Flows (Desktop 1280x800 + Mobile 390x844).
 * Verifies:
 *   Flow 1 (Desktop Owner): Demo Banner + Login + Dashboard (HH.MM shift hrs, plain-English efficiency, Weekly/Monthly P&L)
 *   Flow 2 (Mobile Supervisor): Login + /today Shift Pills + /beams (200 OK, ETA badges, Weft Receipts) + RBAC check
 *   Flow 3 (Desktop Owner): /inspect AITEX Reference Sample -> ONNX + Grad-CAM Heatmap -> Confirm Clean Review saved
 *   Flow 4 (Desktop Owner): /payroll Auto-Preview + Live Damage Cut + /analytics (Forecast, EB Predictor, XLSX Workbook, Simulator)
 */
const { chromium } = require("playwright-core");
const path = require("path");

const BASE = process.env.LOOMOS_URL || "http://127.0.0.1:5173";
const SHOT_DIR = process.env.SHOT_DIR || path.join(__dirname, "screenshots");

function assert(cond, msg) {
  if (!cond) throw new Error(`E2E ASSERTION FAILED: ${msg}`);
}

async function login(page, user, pass) {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  const banner = await page.innerText("body");
  assert(banner.includes("DEMO DATA ACTIVE"), "DEMO DATA banner missing on /login");
  await page.fill('input[autocomplete="username"], input[type="text"]', user);
  await page.fill('input[type="password"]', pass);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(1200);
}

async function runAll() {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const problems = [];

  const attachListeners = (page, tag) => {
    page.on("console", (m) => {
      if (m.type() === "error") problems.push(`[${tag} console.error] ${m.text().slice(0, 200)}`);
    });
    page.on("pageerror", (e) => problems.push(`[${tag} pageerror] ${e.message.slice(0, 200)}`));
    page.on("response", (r) => {
      if (r.status() >= 400) problems.push(`[${tag} http ${r.status()}] ${r.request().method()} ${r.url().replace(BASE, "")}`);
    });
  };

  try {
    // --- FLOW 1: Desktop Owner Dashboard + All Pages Sweep ---
    const ctx1 = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const p1 = await ctx1.newPage();
    attachListeners(p1, "flow1_owner_desktop");
    await login(p1, "welcome123", "welcome123");
    assert(p1.url().includes("/dashboard"), `Expected /dashboard, got ${p1.url()}`);
    await p1.waitForSelector("text=Machine Running & Weaving Speed Efficiency");
    const dashTxt = await p1.innerText("body");
    assert(dashTxt.includes("shift hrs ran"), "Dashboard missing HH.MM shift hrs ran");
    assert(!dashTxt.includes("Simple formula:"), "Dashboard should not show formula text");
    assert(dashTxt.includes("₹7560.00"), "Dashboard Weekly Financial Summary missing non-zero EB bill ₹7560.00");
    await p1.screenshot({ path: path.join(SHOT_DIR, "flow1_dashboard.png"), fullPage: true });

    // Check Monthly toggle works
    await p1.click('button:has-text("Monthly (30d)")');
    await p1.waitForTimeout(700);
    const monthTxt = await p1.innerText("body");
    assert(monthTxt.includes("Monthly Output"), "Monthly toggle did not activate");
    console.log("PASS Flow 1: Owner Desktop Login + Dashboard (Weekly/Monthly + HH.MM hrs + EB)");

    // --- FLOW 3: Owner /inspect ONNX + Grad-CAM + Review ---
    await p1.goto(`${BASE}/inspect`, { waitUntil: "networkidle" });
    await p1.waitForSelector("text=AITEX Reference Sample");
    await p1.click('button:has-text("Broken End")');
    await p1.waitForSelector("text=AI Heatmap & Review", { timeout: 10000 });
    await p1.waitForTimeout(500);
    await p1.screenshot({ path: path.join(SHOT_DIR, "flow3_inspect_gradcam.png"), fullPage: true });
    await p1.click('button:has-text("Confirm Clean Cloth")');
    await p1.click('button:has-text("Save Confirmed Review")');
    await p1.waitForSelector("text=Saved Confirmed Clean Cloth");
    console.log("PASS Flow 3: /inspect ONNX + Grad-CAM + Review Persistence");

    // --- FLOW 4: Owner /payroll Live Damage Cut + /analytics + XLSX + Simulator ---
    await p1.goto(`${BASE}/payroll`, { waitUntil: "networkidle" });
    await p1.waitForSelector("text=Payroll Preview");
    await p1.screenshot({ path: path.join(SHOT_DIR, "flow4_payroll.png"), fullPage: true });

    await p1.goto(`${BASE}/analytics`, { waitUntil: "networkidle" });
    await p1.waitForSelector("text=Next 7-Day Cloth Production Forecast");
    await p1.screenshot({ path: path.join(SHOT_DIR, "flow4_analytics_forecast.png"), fullPage: true });
    await p1.click('button:has-text("2. EB Bill & Power Efficiency")');
    await p1.waitForSelector("text=Next Bi-Monthly EB Bill Predictor");
    await p1.waitForSelector("text=TNPDCL EB Bill Calculator");
    await p1.waitForSelector("text=Payable EB Bill");
    await p1.click('button:has-text("79 kWh (Free)")');
    await p1.waitForSelector("text=Free Quota Applied");
    await p1.click('button:has-text("6,361 kWh")');
    await p1.waitForSelector("text=Payable EB Bill");
    await p1.click('button:has-text("By Fabric Metres (m)")');
    await p1.waitForSelector("text=EB Cost:");
    await p1.screenshot({ path: path.join(SHOT_DIR, "flow4_eb_efficiency.png"), fullPage: true });
    await p1.waitForSelector("text=EB Bill vs. Metres Produced");
    await p1.click('button:has-text("3. Excel")');
    await p1.waitForSelector("text=Download 7-Sheet Excel");
    await p1.click('button:has-text("4. Loom Expansion Simulator")');
    await p1.waitForSelector("text=20 / 30 / 50 / 100 Loom Preset Comparison");
    await p1.click('button:has-text("50 Looms")');
    await p1.waitForTimeout(500);
    await p1.screenshot({ path: path.join(SHOT_DIR, "flow4_simulator.png"), fullPage: true });

    // Visit remaining Owner pages to confirm zero errors & capture screenshots
    for (const pg of ["/today", "/beams", "/deliveries", "/settings", "/audit-log"]) {
      await p1.goto(`${BASE}${pg}`, { waitUntil: "networkidle" });
      await p1.waitForTimeout(500);
      await p1.screenshot({ path: path.join(SHOT_DIR, `owner_${pg.slice(1)}.png`), fullPage: true });
    }
    const beamsTxt = await p1.goto(`${BASE}/beams`, { waitUntil: "networkidle" }).then(() => p1.innerText("body"));
    assert(!beamsTxt.includes("Remaining: 0.00 m (100%)") || beamsTxt.includes("BM-100"), "Beams check");
    assert(beamsTxt.includes("ETA:"), "Beams missing Phase 3 ETA badge");
    console.log("PASS Flow 4: /payroll Live Preview + /analytics (Forecast, EB, Reports, 50-Loom Sim) + All Owner Pages");
    await ctx1.close();

    // --- FLOW 2: Mobile Supervisor (/today + /beams 200 OK + /inspect + /analytics + RBAC) ---
    const ctx2 = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const p2 = await ctx2.newPage();
    attachListeners(p2, "flow2_sup_mobile");
    await login(p2, "sup_siva", "supPassword1");
    assert(p2.url().includes("/today"), `Supervisor expected /today, got ${p2.url()}`);
    await p2.waitForSelector('button:has-text("Shift 1 (Day)")');
    const todayTxt = await p2.innerText("body");
    assert(todayTxt.includes("125.0 m"), "Today Shift 1 should prefill 125.0 m instead of blank Shift 2");
    await p2.screenshot({ path: path.join(SHOT_DIR, "flow2_sup_mobile_today.png"), fullPage: true });

    await p2.goto(`${BASE}/beams`, { waitUntil: "networkidle" });
    await p2.waitForTimeout(600);
    const supBeamsTxt = await p2.innerText("body");
    assert(!supBeamsTxt.includes("Owner role required"), "Supervisor got 403 on /beams!");
    assert(supBeamsTxt.includes("BM-101") && supBeamsTxt.includes("ETA:"), "Supervisor /beams missing active beams or ETA");
    await p2.screenshot({ path: path.join(SHOT_DIR, "flow2_sup_mobile_beams.png"), fullPage: true });

    // Supervisor blocked from /payroll -> redirected to /today without 403
    await p2.goto(`${BASE}/payroll`, { waitUntil: "networkidle" });
    assert(p2.url().includes("/today"), "Supervisor should redirect off /payroll");
    await p2.goto(`${BASE}/inspect`, { waitUntil: "networkidle" });
    await p2.waitForSelector("text=AITEX Reference Sample");
    await p2.goto(`${BASE}/analytics`, { waitUntil: "networkidle" });
    await p2.waitForSelector("text=Next 7-Day Cloth Production Forecast");
    console.log("PASS Flow 2: Mobile Supervisor /today (125.0m) + /beams (200 OK, ETA) + /inspect + /analytics + RBAC");
    await ctx2.close();
  } finally {
    await browser.close();
  }

  console.log(`TOTAL E2E PROBLEMS: ${problems.length}`);
  if (problems.length > 0) {
    for (const pr of problems) console.error("  " + pr);
    process.exit(1);
  }
}

runAll().catch((err) => {
  console.error(err);
  process.exit(1);
});
