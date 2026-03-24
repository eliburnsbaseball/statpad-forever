import process from "node:process";

async function main() {
  let chromium;
  try {
    ({ chromium } = await import("playwright"));
  } catch (err) {
    console.error("Missing dependency: playwright");
    console.error("Install with: npm i -D playwright");
    process.exit(1);
  }

  const urls = process.argv.slice(2).filter(Boolean);
  if (!urls.length) {
    console.error("Usage: node scripts/scrape_rendered_images.mjs <url> [url...]");
    process.exit(1);
  }

  const browser = await chromium.launch({ headless: true });
  try {
    for (const url of urls) {
      const page = await browser.newPage({
        viewport: { width: 1440, height: 2000 },
        userAgent:
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      });
      const found = new Set();
      page.on("response", async (response) => {
        try {
          const ct = (response.headers()["content-type"] || "").toLowerCase();
          if (ct.startsWith("image/")) found.add(response.url());
        } catch {}
      });
      await page.goto(url, { waitUntil: "networkidle", timeout: 120000 });
      await page.waitForTimeout(2500);

      const domImages = await page.evaluate(() => {
        const out = new Set();
        document.querySelectorAll("img").forEach((img) => {
          if (img.currentSrc) out.add(img.currentSrc);
          else if (img.src) out.add(img.src);
          const srcset = img.getAttribute("srcset") || "";
          srcset
            .split(",")
            .map((part) => part.trim().split(/\s+/)[0])
            .filter(Boolean)
            .forEach((src) => out.add(src));
        });
        document.querySelectorAll("*").forEach((el) => {
          const style = window.getComputedStyle(el);
          [style.backgroundImage, style.content].forEach((value) => {
            if (!value || value === "none") return;
            const matches = value.match(/url\((['"]?)(.*?)\1\)/g) || [];
            matches.forEach((match) => {
              const raw = match.replace(/^url\((['"]?)/, "").replace(/(['"]?)\)$/, "");
              if (raw) out.add(raw);
            });
          });
        });
        return Array.from(out);
      });

      domImages.forEach((u) => found.add(u));
      const list = Array.from(found)
        .filter((u) => /^https?:\/\//i.test(u))
        .sort();

      console.log(JSON.stringify({ url, images: list }, null, 2));
      await page.close();
    }
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
