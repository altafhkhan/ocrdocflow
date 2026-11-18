// Takes the Google Play phone screenshots (1080 x 1920) from the web app
// running on the local dev server, made to behave like the Android app.
//   node shoot.mjs <email> <password> <outDir> <invoiceToUpload>
import puppeteer from "puppeteer-core";
import fs from "node:fs";

const [email, password, outDir, uploadFile] = process.argv.slice(2);
const APP = "http://localhost:5173";
const API = "http://localhost:8000";
fs.mkdirSync(outDir, { recursive: true });

// The sign-in token is passed in (the test server limits repeated logins).
const token = process.env.DEMO_TOKEN;
if (!token) throw new Error("set DEMO_TOKEN");

const browser = await puppeteer.launch({
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
  userDataDir: "D:/Android/tmp/shots-tool/profile",
  args: ["--no-first-run", "--disk-cache-dir=D:/Android/tmp/shots-tool/cache"],
});
const page = await browser.newPage();
await page.setViewport({ width: 432, height: 768, deviceScaleFactor: 2.5, isMobile: true, hasTouch: true });
// Make the page believe it runs inside the Android app, and sign it in.
await page.evaluateOnNewDocument((t) => {
  window.androidBridge = { postMessage() {} };
  localStorage.setItem("token", t);
}, token);

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const shot = async (name) => {
  await page.screenshot({ path: `${outDir}/${name}.png` });
  console.log("saved", name);
};
const clickText = (text, last = false) =>
  page.evaluate((text, last) => {
    const all = [...document.querySelectorAll("button")].filter((b) => b.innerText.trim().startsWith(text));
    const b = last ? all[all.length - 1] : all[0];
    if (b) b.click();
    return !!b;
  }, text, last);

await page.goto(`${APP}/dashboard`, { waitUntil: "networkidle0" });
await wait(800);

// Save the two oldest invoices so the list shows both "saved" and "done".
for (let i = 0; i < 2; i++) {
  const state = await page.evaluate((i) => {
    const rows = [...document.querySelectorAll("table tbody tr")];
    const row = rows[i];
    if (!row || row.innerText.includes("saved")) return "skip";
    [...row.querySelectorAll("button")].pop().click();
    return "opened";
  }, i);
  if (state === "opened") {
    await wait(4000);
    await clickText("Save");
    await wait(3500);
    await clickText("Cancel");
    await page.evaluate(() => [...document.querySelectorAll("button")].find((b) => b.innerText.trim() === "✕")?.click());
    await wait(800);
  }
}
await page.goto(`${APP}/dashboard`, { waitUntil: "networkidle0" });
await wait(800);
await shot("01-dashboard");
await page.evaluate(() => {
  [...document.querySelectorAll("button")].find((b) => b.innerText.startsWith("Upload History"))?.scrollIntoView({ block: "start" });
  window.scrollBy(0, -12);
});
await wait(500);
await shot("02-history");
await page.evaluate(() => window.scrollTo(0, 0));

// Upload in progress: the scanning bar and the progress line. The upload
// request is held back and then cancelled, so nothing new is stored.
if (uploadFile) {
  let held = null;
  await page.setRequestInterception(true);
  page.on("request", (req) => {
    if (req.method() === "POST" && req.url().includes("/documents/upload")) held = req;
    else req.continue();
  });
  const input = await page.$('input[type=file]:not([capture])');
  await input.uploadFile(uploadFile);
  await wait(2600);
  await shot("03-reading");
  if (held) await held.abort();
  await wait(500);
  page.removeAllListeners("request");
  await page.setRequestInterception(false);
  await page.goto(`${APP}/dashboard`, { waitUntil: "networkidle0" });
  await wait(800);
}

// Review screen: original document beside the fields.
await page.evaluate(() => {
  const rows = [...document.querySelectorAll("table tbody tr")];
  [...rows[rows.length - 1].querySelectorAll("button")].pop().click();
});
await wait(6000);
await shot("04-review-original");
await clickText("Hide original");
await wait(800);
await shot("05-review-fields");
await clickText("Cancel");
await page.evaluate(() => [...document.querySelectorAll("button")].find((b) => b.innerText.trim() === "✕")?.click());
await wait(600);

// Export panel.
await clickText("Download invoices");
await wait(1200);
await page.evaluate(() => {
  document.querySelector("input[value=xlsx]")?.click();
  [...document.querySelectorAll("button")].find((b) => b.innerText.startsWith("Download invoices"))?.scrollIntoView({ block: "start" });
});
await wait(800);
await shot("06-export");

await browser.close();
