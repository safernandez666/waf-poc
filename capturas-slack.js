// Captura del webhook recibiendo la alerta del bridge.
const { chromium } = require('playwright');

(async () => {
  const uuid = require('fs').readFileSync('/tmp/wh-url.txt', 'utf8').trim().split('/').pop();
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  await page.goto(`https://webhook.site/#!/view/${uuid}`, { waitUntil: 'networkidle' });
  // esperar la fila del POST
  await page.waitForSelector('text=POST', { timeout: 30000 });
  await page.waitForTimeout(2500);
  // abrir el request para mostrar el contenido JSON
  try {
    await page.click('text=POST', { timeout: 5000 });
    await page.waitForTimeout(1500);
  } catch { /* la lista ya muestra suficiente */ }
  await page.screenshot({ path: '/Users/santiago/Downloads/waf-poc/capturas/26-bonus-slack-webhook.png' });
  console.log('OK captura');
  await browser.close();
})();
