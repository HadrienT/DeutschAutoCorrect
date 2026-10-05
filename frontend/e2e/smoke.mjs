// End-to-end smoke test + screenshots. Usage: BASE=http://localhost:8000 node e2e/smoke.mjs
// Requires a running backend with a demo recording (make demo) and Playwright (global install ok).
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = (() => { try { return require("playwright"); } catch { return require("/node-tools/node_modules/playwright"); } })();

const BASE = process.env.BASE ?? "http://localhost:8000";
const OUT = process.env.OUT ?? "../docs/screenshots";
const exe = process.env.CHROMIUM ?? undefined;
const assert = (c, m) => { if (!c) { console.error("FAIL:", m); process.exitCode = 1; } else console.log("ok  :", m); };

const browser = await chromium.launch({ executablePath: exe, args: ["--autoplay-policy=no-user-gesture-required"] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "light" });
const page = await ctx.newPage();
const logs = [];
page.on("pageerror", (e) => logs.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") logs.push(m.text()); });

await page.goto(BASE);
await page.waitForSelector("[data-testid=rec-card]");
assert((await page.locator("[data-testid=rec-card]").count()) >= 1, "library lists the demo recording");
await page.screenshot({ path: `${OUT}/01-library.png` });

await page.locator("[data-testid=rec-card] a").nth(1).click();
await page.waitForSelector("[data-testid=error-card]");
await page.waitForTimeout(600);
const total = async () => (await page.locator("[data-testid=grade-total] .grade-num").innerText()).replace(",", ".");
const before = Number(await total());
const cards = await page.locator("[data-testid=error-card]").count();
assert(cards >= 8, `error list populated (${cards})`);
const groups = await page.locator(".group-head").allInnerTexts();
assert(groups.length === 4, `4 category groups: ${groups.map((g) => g.replace(/\s+/g, " ")).join(" | ")}`);
await page.screenshot({ path: `${OUT}/02-recording.png` });

// clickable timecode seeks the audio (find the 2nd+ error to avoid 0)
const card = page.locator("[data-testid=error-card]").nth(3);
const tcText = await card.locator(".tc").first().innerText();
await card.locator(".tc").first().click();
await page.waitForTimeout(400);
const clock = await page.locator(".player-top .mono").first().innerText();
const [mm, ss] = tcText.replace("▶", "").trim().split(":");
const target = Number(mm) * 60 + Number(ss);
const shown = clock.split("/")[0].trim().split(":");
const now = Number(shown[0]) * 60 + Number(shown[1]);
assert(Math.abs(now - Math.max(0, target - 0.8)) < 2.5, `timecode ${tcText} seeks playhead (now ${now.toFixed(1)}s, target ${target.toFixed(1)}s)`);
assert(await page.locator(".err-card.sel").count() === 1, "clicked error becomes selected");

// rejecting a grave error raises (or keeps) the grade
await page.locator("button.sev.bad").first().locator("xpath=ancestor::div[contains(@class,'err-card')]").locator("button[aria-label='Rejeter l\\'erreur']").click();
await page.waitForTimeout(500);
const after = Number(await total());
assert(after >= before, `rejecting an error does not lower the grade (${before} → ${after})`);

// manual criterion
const manual = page.locator("input[aria-label='Points saisis']");
for (const v of ["0", "2"]) { await manual.fill(v); await manual.press("Enter"); await page.waitForTimeout(500); }
const withManual = Number(await total());
assert(withManual > after - 5 && withManual >= Number(await total()), `manual points applied (grade ${withManual})`);
await manual.fill("0"); await manual.press("Enter"); await page.waitForTimeout(500);
const zero = Number(await total());
assert(withManual > zero, `manual points raise the grade (${zero} → ${withManual})`);

// keyboard: K selects next error
await page.keyboard.press("k");
await page.waitForTimeout(300);
assert(await page.locator(".err-card.sel").count() === 1, "keyboard K selects an error");
await page.screenshot({ path: `${OUT}/03-recording-selected.png` });

// rubrics page
await page.goto(`${BASE}/#/rubrics`);
await page.waitForSelector("[data-testid=criterion]");
await page.waitForSelector("[data-testid=preview]");
const prev0 = (await page.locator("[data-testid=preview] .grade-num").innerText());
await page.locator("[data-testid=criterion]").first().locator("input[type=number]").nth(1).fill("0"); // penalty minor
await page.waitForTimeout(700);
await page.screenshot({ path: `${OUT}/04-rubrics.png` });
const prev1 = (await page.locator("[data-testid=preview] .grade-num").innerText());
assert(prev0 !== "" && prev1 !== "", `rubric preview live (${prev0} → ${prev1})`);

// dark + mobile
await page.goto(`${BASE}/#/`);
const dark = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "dark" });
const dp = await dark.newPage();
await dp.goto(BASE); await dp.waitForSelector("[data-testid=rec-card]");
await dp.locator("[data-testid=rec-card] a").nth(1).click();
await dp.waitForSelector("[data-testid=error-card]"); await dp.waitForTimeout(600);
await dp.screenshot({ path: `${OUT}/05-recording-dark.png` });
const mob = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
const mp = await mob.newPage();
await mp.goto(BASE); await mp.waitForSelector("[data-testid=rec-card]");
await mp.locator("[data-testid=rec-card] a").nth(1).click();
await mp.waitForSelector("[data-testid=error-card]"); await mp.waitForTimeout(600);
const overflow = await mp.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
assert(!overflow, "no horizontal overflow on mobile");
await mp.screenshot({ path: `${OUT}/06-recording-mobile.png` });

assert(logs.length === 0, `no console errors ${logs.join(" / ")}`);
await browser.close();
