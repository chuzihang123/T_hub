// Attach to a running MCHOSE HUB (started with --remote-debugging-port=9222),
// hook the WebHID calls in its renderer, and print every HID byte it exchanges.
//
//   node hub-hook.js [seconds]
//
// The headset page has to be opened for traffic to appear. Ctrl+C to stop.

const PORT = 9222;
const DURATION = (parseInt(process.argv[2] || "180", 10) || 180) * 1000;

const HOOK = `(() => {
  if (window.__hidHooked) return 'already';
  window.__hidHooked = true;
  window.__hidlog = [];
  const log = (o) => { window.__hidlog.push(o); if (window.__hidlog.length > 300) window.__hidlog.shift(); };
  const P = HIDDevice.prototype;
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
  if (navigator.hid) {
    navigator.hid.getDevices().then((ds) => ds.forEach((d) => {
      d.addEventListener('inputreport', (e) => log({ t: 'input', id: e.reportId, d: Array.from(new Uint8Array(e.data.buffer)) }));
    }));
  }
  return 'hooked';
})()`;

const hex = (arr) => (arr || []).map((b) => b.toString(16).padStart(2, "0")).join(" ");

async function main() {
  const targets = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const page = targets.find((t) => t.type === "page" && /mchose/i.test(t.url || "")) || targets.find((t) => t.type === "page");
  if (!page) {
    console.error("no page target found; is HUB running with the debug port?");
    process.exit(1);
  }
  console.log("attached:", page.title || page.url);

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();

  const send = (method, params) =>
    new Promise((resolve, reject) => {
      const mid = ++id;
      pending.set(mid, { resolve, reject });
      ws.send(JSON.stringify({ id: mid, method, params: params || {} }));
    });

  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const p = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) p.reject(new Error(JSON.stringify(msg.error)));
      else p.resolve(msg.result);
    }
  };

  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  await send("Runtime.enable");
  await send("Page.enable");

  // install before any app script runs, so the very first battery read is caught
  await send("Page.addScriptToEvaluateOnNewDocument", { source: HOOK });
  const hookRes = await send("Runtime.evaluate", { expression: HOOK, returnByValue: true });
  console.log("hook:", hookRes.result && hookRes.result.value);

  if (process.env.NO_RELOAD !== "1") {
    console.log("reloading the renderer to force a fresh battery read...");
    await send("Page.reload", { ignoreCache: false });
    await new Promise((r) => setTimeout(r, 3500));
  }

  const seen = new Set();
  const deadline = Date.now() + DURATION;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 700));
    try {
      const r = await send("Runtime.evaluate", {
        expression: "JSON.stringify((window.__hidlog||[]).slice(-60))",
        returnByValue: true,
      });
      const list = JSON.parse((r.result && r.result.value) || "[]");
      list.forEach((e) => {
        const key = e.t + "|" + e.id + "|" + hex(e.d);
        if (seen.has(key)) return;
        seen.add(key);
        console.log(`${e.t.padEnd(20)} id=0x${(e.id || 0).toString(16).padStart(2, "0")}  ${hex(e.d)}`);
      });
    } catch (e) {
      // page might be navigating; keep polling
    }
  }
  ws.close();
}

main().catch((e) => { console.error(e); process.exit(1); });
