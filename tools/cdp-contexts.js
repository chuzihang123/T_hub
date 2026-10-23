// List CDP execution contexts of a renderer (main world + Electron isolated world).
//   node cdp-contexts.js <port> [reload]

const [port, reload] = [process.argv[2], process.argv[3] === "reload"];

async function main() {
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const page = targets.find((t) => t.type === "page");
  if (!page) throw new Error("no page");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();
  const send = (method, params) => new Promise((resolve, reject) => {
    const mid = ++id;
    pending.set(mid, { resolve, reject });
    ws.send(JSON.stringify({ id: mid, method, params: params || {} }));
  });
  const contexts = [];
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.method === "Runtime.executionContextCreated") contexts.push(msg.params.context);
    if (msg.id && pending.has(msg.id)) {
      const p = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? p.reject(new Error(JSON.stringify(msg.error))) : p.resolve(msg.result);
    }
  };
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  await send("Runtime.enable");
  await send("Page.enable");
  if (reload) {
    await send("Page.reload", { ignoreCache: false });
    await new Promise((r) => setTimeout(r, 4000));
  } else {
    await new Promise((r) => setTimeout(r, 1500));
  }
  contexts.forEach((c) => {
    console.log(`id=${c.id} name=${JSON.stringify(c.name)} origin=${c.origin} aux=${JSON.stringify(c.auxData)}`);
  });
  ws.close();
}

main().catch((e) => { console.error(e); process.exit(1); });
