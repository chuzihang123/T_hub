// Generic WebHID sniffer: attach to a Chromium page, inject the HID hook before
// any app script runs, then print every HID exchange it makes.
//
//   node web-hook.js <port> [seconds]
//
// The page still needs you to click its own "connect / select device" button and
// pick the device in Chrome's chooser — that permission prompt cannot be scripted.

const PORT = parseInt(process.argv[2] || "9333", 10);
const DURATION = (parseInt(process.argv[3] || "240", 10) || 240) * 1000;
const FILTER = process.argv[4] || "";

const HOOK = `(() => {
  if (window.__hidHooked) return 'already';
  window.__hidHooked = true;
  window.__hidlog = [];
  const log = (o) => { window.__hidlog.push(o); if (window.__hidlog.length > 400) window.__hidlog.shift(); };
  const P = window.HIDDevice && HIDDevice.prototype;
  if (!P) return 'no-webhid';
  const wrapOut = (name) => {
    const orig = P[name];
    if (!orig) return;
    P[name] = function () {
      try {
        const id = arguments[0], data = arguments[1];
        log({ t: name, id: id, d: data ? Array.from(new Uint8Array(data.buffer || data)) : null });
      } catch (e) {}
      return orig.apply(this, arguments);
    };
  };
  wrapOut('sendReport');
  wrapOut('sendFeatureReport');
  const wrapIn = (name) => {
    const orig = P[name];
    if (!orig) return;
    P[name] = async function () {
      const r = await orig.apply(this, arguments);
      try { log({ t: name, id: arguments[0], d: r && r.buffer ? Array.from(new Uint8Array(r.buffer)) : null }); } catch (e) {}
      return r;
    };
  };
  wrapIn('receiveFeatureReport');
  wrapIn('receiveReport');
  const attach = () => {
    if (!navigator.hid) return;
    navigator.hid.getDevices().then((ds) => ds.forEach((d) => {
      if (d.__hooked) return;
      d.__hooked = true;
      d.addEventListener('inputreport', (e) => log({ t: 'input', id: e.reportId, d: Array.from(new Uint8Array(e.data.buffer)) }));
    }));
  };
  attach();
  setInterval(attach, 1500);
  return 'hooked';
})()`;

const hex = (arr) => (arr || []).map((b) => b.toString(16).padStart(2, "0")).join(" ");

async function main() {
  const targets = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const pages = targets.filter((t) => t.type === "page" && !/^(devtools|chrome)/.test(t.url || ""));
  const page = (FILTER && pages.find((t) => (t.url || "").includes(FILTER))) || pages[0];
  if (!page) { console.error("no page target"); process.exit(1); }
  console.log("attached:", page.url);

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();
  const send = (method, params) => new Promise((resolve, reject) => {
    const mid = ++id;
    pending.set(mid, { resolve, reject });
    ws.send(JSON.stringify({ id: mid, method, params: params || {} }));
  });
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const p = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? p.reject(new Error(JSON.stringify(msg.error))) : p.resolve(msg.result);
    }
  };
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Page.addScriptToEvaluateOnNewDocument", { source: HOOK });
  const hookRes = await send("Runtime.evaluate", { expression: HOOK, returnByValue: true });
  console.log("hook:", hookRes.result && hookRes.result.value);

  const seen = new Set();
  const deadline = Date.now() + DURATION;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 700));
    try {
      const r = await send("Runtime.evaluate", {
        expression: "JSON.stringify((window.__hidlog||[]).slice(-80))",
        returnByValue: true,
      });
      const list = JSON.parse((r.result && r.result.value) || "[]");
      list.forEach((e) => {
        const key = e.t + "|" + e.id + "|" + hex(e.d);
        if (seen.has(key)) return;
        seen.add(key);
        console.log(`${e.t.padEnd(20)} id=0x${(e.id || 0).toString(16).padStart(2, "0")}  ${hex(e.d)}`);
      });
    } catch (e) { /* navigating */ }
  }
  ws.close();
}

main().catch((e) => { console.error(e); process.exit(1); });
