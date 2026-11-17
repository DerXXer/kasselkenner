// Jede Folie der Startseite bei vielen Fenstergrößen: Überschrift unter Kopf? Text über Polaroids?
// Vorher im docs-Ordner: python3 -m http.server 8765 ; dann: node werkzeuge/titelbild_messen.mjs
import { spawn } from "node:child_process";
import { writeFileSync, mkdirSync } from "node:fs";
const PORT = 9335, BASIS = "http://127.0.0.1:8765/";
const GROESSEN = [[1920, 1080], [1600, 634], [1440, 620], [1280, 600], [1024, 600], [1366, 768], [1280, 720], [1000, 600], [800, 600], [768, 1024], [430, 932], [390, 844], [360, 640]];
mkdirSync("/tmp/kk-held/dias", { recursive: true });
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", ["--headless=new", `--remote-debugging-port=${PORT}`, "--user-data-dir=/tmp/kk-dias-chrome", "--hide-scrollbars", "--no-first-run", "--window-size=1920,1200", "about:blank"], { stdio: "ignore" });
const warte = (ms) => new Promise((r) => setTimeout(r, ms));
let ws;
for (let i = 0; i < 50; i++) { try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); const p = l.find((t) => t.type === "page"); if (p) { ws = p.webSocketDebuggerUrl; break; } } catch {} await warte(200); }
const sock = new WebSocket(ws); await new Promise((r) => sock.addEventListener("open", r));
let nr = 0; const offen = new Map();
sock.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && offen.has(m.id)) { offen.get(m.id)(m); offen.delete(m.id); } });
const cdp = (method, params = {}) => new Promise((r, f) => { const id = ++nr; offen.set(id, (m) => m.error ? f(new Error(method + ": " + m.error.message)) : r(m.result)); sock.send(JSON.stringify({ id, method, params })); });
const js = async (a) => { const r = await cdp("Runtime.evaluate", { expression: a, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails)); return r.result.value; };
await cdp("Page.enable");
let probleme = 0;
for (const [w, h] of GROESSEN) {
  await cdp("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 768 });
  await cdp("Page.navigate", { url: BASIS }); await warte(1300);
  const n = await js("document.querySelectorAll('.dia').length");
  for (let i = 0; i < n; i++) {
    const m = await js(`(() => {
      const d = [...document.querySelectorAll('.dia')]; d.forEach((x, j) => x.classList.toggle('an', j === ${i}));
      const kopf = [...document.querySelectorAll('.kopf, .themen')].reduce((b, e) => Math.max(b, e.getBoundingClientRect().bottom), 0);
      const t = d[${i}].querySelector('.text'); const g = t.querySelector('.gross').getBoundingClientRect();
      const teile = [...t.querySelectorAll('.dach, .gross, .knopf')].map(e => e.getBoundingClientRect());
      const pol = [...document.querySelectorAll('.reiter button')].map(e => e.getBoundingClientRect()).filter(r => r.width > 0 && getComputedStyle(document.querySelector('.reiter img')).display !== 'none');
      const kreuz = teile.some(a => pol.some(b => !(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top)));
      return { titel: t.querySelector('.gross').textContent.trim().slice(0, 40), oben: Math.round(g.top), kopf: Math.round(kopf), kreuz };
    })()`);
    const fehler = m.oben < m.kopf + 8 || m.kreuz;
    if (fehler) { probleme++; console.log("PROBLEM", `${w}x${h}`, JSON.stringify(m)); const r = await cdp("Page.captureScreenshot", { format: "png" }); writeFileSync(`/tmp/kk-held/dias/${w}x${h}_${i}.png`, Buffer.from(r.data, "base64")); }
  }
  if (w === 1600 || w === 1024) { await js(`(() => { const d=[...document.querySelectorAll('.dia')]; d.forEach((x,j)=>x.classList.toggle('an', j===1)); })()`); const r = await cdp("Page.captureScreenshot", { format: "png" }); writeFileSync(`/tmp/kk-held/dias/beispiel_${w}x${h}.png`, Buffer.from(r.data, "base64")); }
}
console.log("Probleme gesamt:", probleme);
chrome.kill(); process.exit(0);
