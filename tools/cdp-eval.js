// Evaluate an expression in the first page target of a CDP-enabled Chromium/Electron.
//   node cdp-eval.js <port> "<expression>"

const [port, expr] = [process.argv[2], process.argv[3]];

async function main() {
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const page = targets.find((t) => t.type === "page") || targets[0];
  if (!page) throw new Error("no page");
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
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) console.error("exception:", JSON.stringify(r.exceptionDetails).slice(0, 500));
  console.log(JSON.stringify(r.result && r.result.value, null, 2));
  ws.close();
}

main().catch((e) => { console.error(e); process.exit(1); });
