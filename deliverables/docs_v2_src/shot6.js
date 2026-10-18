// Screenshot 5.6 for the project report: the Version 2 result page (anonymous, so no account details).
const puppeteer = require("puppeteer-core");
const OUT = process.argv[2];
const TEXT = "The Eiffel Tower is in Paris. It was completed in 1925. Albert Einstein developed the theory of relativity. " +
  "The Great Wall of China is visible from the Moon with the naked eye.";
(async () => {
  const browser = await puppeteer.launch({ executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    headless: true, args: ["--no-first-run", "--no-default-browser-check"] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1100, height: 900, deviceScaleFactor: 2 });
  await page.goto("http://localhost:5173/analyse", { waitUntil: "networkidle2", timeout: 60000 });
  await page.waitForSelector("#passage", { timeout: 60000 });
  const mode = await page.evaluate(() => document.querySelector('[role="status"]')?.textContent || "");
  console.log("status pill:", mode);
  await page.type("#passage", TEXT);
  const buttons = await page.$$("button");
  for (const b of buttons) if ((await b.evaluate(e => e.textContent.trim())) === "Analyse") { await b.click(); break; }
  await page.waitForSelector("#claims", { timeout: 300000 });
  await new Promise(r => setTimeout(r, 1500));
  // from the marked text to the end of the first three claim cards
  const box = await page.evaluate(() => {
    const top = document.querySelector('section[aria-labelledby="marked"]').getBoundingClientRect().top + window.scrollY;
    const cards = [...document.querySelectorAll("#claims ~ div li, section[aria-labelledby=claims] li")];
    const last = cards[Math.min(2, cards.length - 1)].getBoundingClientRect();
    const left = document.querySelector('section[aria-labelledby="marked"]').getBoundingClientRect().left;
    const width = document.querySelector('section[aria-labelledby="marked"]').getBoundingClientRect().width;
    return { x: left - 12, y: top - 12, width: width + 24, height: last.bottom + window.scrollY - top + 24, cards: cards.length };
  });
  console.log("claim cards:", box.cards);
  await page.screenshot({ path: OUT, clip: { x: box.x, y: box.y, width: box.width, height: box.height }, captureBeyondViewport: true });
  await browser.close();
  console.log("saved", OUT);
})().catch(e => { console.error(e); process.exit(1); });
