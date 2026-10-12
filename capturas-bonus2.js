// Capturas de las secciones nuevas del bonus: latencia, PL2, scores de telemetria.
const { chromium } = require('playwright');
const fs = require('fs');

function termPage(file) {
  const t = fs.readFileSync(file, 'utf8');
  return `<!doctype html><html><head><meta charset=utf-8><style>
body{background:#0d1117;margin:0;padding:24px;font:13px/1.55 "SF Mono",Menlo,Consolas,monospace}
pre{color:#c9d1d9;margin:0;white-space:pre-wrap}
</style></head><body><pre>${t.replace(/&/g,'&amp;').replace(/</g,'&lt;')}</pre></body></html>`;
}

// rules: [[regexSource, color], ...] — se serializa y se compila adentro de la pagina
function makeHighlighter(rules) {
  return (l) => {
    const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
    for (const [src, color] of rules) {
      if (new RegExp(src).test(l)) return `<span style="color:${color}">${esc(l)}</span>`;
    }
    return esc(l);
  };
}

(async () => {
  const browser = await chromium.launch();
  const C = '/Users/santiago/Downloads/waf-poc/capturas';

  async function shot(file, out, width, rules) {
    const p = await browser.newPage({ viewport: { width, height: 600 } });
    fs.writeFileSync('/tmp/shot.html', termPage(file));
    await p.goto('file:///tmp/shot.html');
    await p.waitForTimeout(300);
    await p.evaluate((rulesSrc) => {
      const pre = document.querySelector('pre');
      const hl = eval(`(${rulesSrc.highlighter})`)(rulesSrc.rules);
      pre.innerHTML = pre.textContent.split('\n').map(hl).join('\n');
    }, { highlighter: makeHighlighter.toString(), rules });
    await p.screenshot({ path: `${C}/${out}`, fullPage: true });
    console.log('OK', out);
    await p.close();
  }

  await shot('/tmp/exp4-latencia.txt', '23-bonus-overhead-latencia.png', 1150, [
    ['^#', '#8b949e'],
    ['^\\$ (?!#)', '#a5d6ff'],
    ['^escenario|^sin WAF|^con WAF|^bloqueado', '#3fb950'],
    ['req/s', '#3fb950'],
    ['indistinguible|no se paga', '#f0883e'],
  ]);

  await shot('/tmp/exp5-pl2.txt', '24-bonus-paranoia-level-2.png', 1150, [
    ['^#', '#8b949e'],
    ['^\\$ (?!#)', '#a5d6ff'],
    ['403\\s*$', '#3fb950'],
    ['^2$', '#f0883e'],
    ['identico', '#f0883e'],
  ]);

  await shot('/tmp/exp6-scores.txt', '25-bonus-anomaly-scores.png', 1150, [
    ['^#', '#8b949e'],
    ['^\\$ (?!#)', '#a5d6ff'],
    ['^payload', '#8b949e'],
    ['-0-0-0', '#f0883e'],
    ['100% del puntaje', '#3fb950'],
  ]);

  await browser.close();
})();
