/**
 * CodeWiki README 截图自动化（T18 v2.2）
 *
 * 加载 GitHub README 渲染页，截取桌面 + 移动两张快照到 assets/screenshots/.
 *
 * 用法：
 *   1. npm install
 *   2. npx playwright install --with-deps chromium
 *   3. npm run screenshot
 *
 * 或通过 GitHub Action 自动跑：.github/workflows/screenshot.yml
 *
 * 输出：assets/screenshots/readme-desktop.png + readme-mobile.png
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const ASSETS_DIR = path.join(PROJECT_ROOT, 'assets', 'screenshots');
const REPO_URL = 'https://github.com/davyzhong/CodeWiki';

const SCREENSHOT_CONFIG = [
  {
    name: 'readme-desktop.png',
    viewport: { width: 1280, height: 800 },
    description: 'CodeWiki README 桌面渲染（1280x800）',
    selector: 'article',
  },
  {
    name: 'readme-mobile.png',
    viewport: { width: 390, height: 844 },
    description: 'CodeWiki README 移动渲染（iPhone 14 视口）',
    selector: 'article',
  },
];

async function main() {
  console.log(`📸 CodeWiki README 截图自动化（Playwright）`);
  console.log(`📂 项目根：${PROJECT_ROOT}`);
  console.log(`🌐 加载：${REPO_URL}\n`);

  if (!fs.existsSync(ASSETS_DIR)) {
    fs.mkdirSync(ASSETS_DIR, { recursive: true });
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();

  let success = 0;
  let failed = 0;

  for (const config of SCREENSHOT_CONFIG) {
    const page = await context.newPage();
    try {
      console.log(`▶ ${config.name}  (${config.viewport.width}x${config.viewport.height})`);
      console.log(`  ${config.description}`);

      await page.setViewportSize(config.viewport);
      await page.goto(REPO_URL, { waitUntil: 'networkidle', timeout: 60000 });
      await page.waitForSelector(config.selector, { timeout: 30000 });
      await page.waitForTimeout(800);

      const outputPath = path.join(ASSETS_DIR, config.name);
      const locator = page.locator(config.selector).first();
      await locator.screenshot({ path: outputPath });
      const size = fs.statSync(outputPath).size;
      console.log(`  ✓ 写入 ${outputPath} (${(size / 1024).toFixed(1)} KB)\n`);
      success++;
    } catch (err) {
      console.error(`  ✗ 失败：${err.message}\n`);
      failed++;
    } finally {
      await page.close();
    }
  }

  await browser.close();

  console.log(`\n📊 总结：成功 ${success} / 失败 ${failed} / 总共 ${SCREENSHOT_CONFIG.length}`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch((err) => {
  console.error('Fatal:', err);
  process.exit(1);
});