// Hook navigator.hid inside Electron's isolated world, reload, and print traffic.
//   node hook-isolated.js <port> [seconds]

const PORT = parseInt(process.argv[2] || "9446", 10);
const DURATION = (parseInt(process.argv[3] || "60", 10) || 60) * 1000;

const HOOK = `(() => {
  if (window.__hidlog2) return 'already';
  window.__hidlog2 = [];
  const log = (o) => { window.__hidlog2.push(o); if (window.__hidlog2.length > 300) window.__hidlog2.shift(); };
  if (!window.HIDDevice) return 'no HIDDevice';
  const P = HIDDevice.prototype;
  ['sendReport','sendFeatureReport'].forEach((n) => {
    const o = P[n]; if (typeof o !== 'function') return;
    P[n] = function () {
      try {
        const id = arguments[0], data = arguments[1];
        log({ t: n, id: id, d: data ? Array.from(new Uint8Array(data.buffer || data)) : null });
      } catch (e) {}
      return o.apply(this, arguments);
    };
  });
  ['receiveReport','receiveFeatureReport'].forEach((n) => {
    const o = P[n]; if (typeof o !== 'function') return;
    P[n] = async function () {
      const r = await o.apply(this, arguments);
      try { log({ t: n + ':reply', id: arguments[0], d: r && r.buffer ? Array.from(new Uint8Array(r.buffer)) : null }); } catch (e) {}
      return r;
    };
  });
  const attach = () => {
    if (!navigator.hid) return;
    navigator.hid.getDevices().then((ds) => (ds || []).forEach((d) => {
      if (d.__w) return;
      d.__w = true;
      d.addEventListener('inputreport', (e) => log({ t: 'input', id: e.reportId, d: Array.from(new Uint8Array(e.data.buffer)) }));
    })).catch(() => {});
  };
  setInterval(attach, 800);
  attach();
  return 'hooked';
})()`;

const hex = (a) => (a || []).map((b) => b.toString(16).padStart(2, "0")).join(" ");

async function main() {
  const targets = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const page = targets.find((t) => t.type === "page");
  if (!page) throw new Error("no page");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();
  let isolatedId = null;
  const send = (method, params) => new Promise((resolve, reject) => {
    const mid = ++id;
    pending.set(mid, { resolve, reject });
    ws.send(JSON.stringify({ id: mid, method, params: params || {} }));
  });
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.method === "Runtime.executionContextCreated") {
      const c = msg.params.context;
      if (c.name === "Electron Isolated Context") isolatedId = c.id;
    }
    if (msg.id && pending.has(msg.id)) {
      const p = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? p.reject(new Error(JSON.stringify(msg.error))) : p.resolve(msg.result);
    }
  };
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  await send("Runtime.enable");
  await send("Page.enable");
  await new Promise((r) => setTimeout(r, 800));

  if (!isolatedId) { console.error("no isolated context"); process.exit(1); }
  console.log("isolated context:", isolatedId);
  const h = await send("Runtime.evaluate", { expression: HOOK, contextId: isolatedId, returnByValue: true });
  console.log("hook:", h.result && h.result.value);

  if (process.env.NO_RELOAD !== "1") {
    console.log("reloading to trigger a fresh device read...");
    await send("Page.reload", { ignoreCache: false });
    await new Promise((r) => setTimeout(r, 4000));
  }

  if (process.env.NO_RELOAD !== "1") {
    isolatedId = null;
    await send("Runtime.enable");
    await new Promise((r) => setTimeout(r, 500));
    if (!isolatedId) console.error("no isolated context after reload");
  }

  const seen = new Set();
  const deadline = Date.now() + DURATION;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 600));
    const ctxs = isolatedId ? [isolatedId] : [];
    for (const cid of ctxs) {
      try {
        const r = await send("Runtime.evaluate", {
          expression: "JSON.stringify(window.__hidlog2||[])",
          contextId: cid, returnByValue: true,
        });
        const list = JSON.parse((r.result && r.result.value) || "[]");
        list.forEach((e) => {
          const key = e.t + "|" + e.id + "|" + hex(e.d);
          if (seen.has(key)) return;
          seen.add(key);
          console.log(`${String(e.t).padEnd(20)} id=0x${(e.id || 0).toString(16).padStart(2, "0")}  ${hex(e.d)}`);
        });
      } catch (e) { /* context gone */ }
    }
  }
  ws.close();
}

main().catch((e) => { console.error(e); process.exit(1); });
