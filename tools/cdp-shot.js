// Navigate a CDP-controlled Chromium page and save a screenshot.
//   node cdp-shot.js <port> <url> <out.png> [waitMs]

const [port, url, out, waitMs] = [process.argv[2], process.argv[3], process.argv[4], process.argv[5]];
const fs = require("fs");

async function main() {
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const page = targets.find((t) => t.type === "page" && !/^(devtools|chrome)/.test(t.url || "")) ||
               targets.find((t) => t.type === "page");
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

  await send("Page.enable");
  await send("Page.navigate", { url });
  await new Promise((r) => setTimeout(r, parseInt(waitMs || "6000", 10)));

  const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  fs.writeFileSync(out, Buffer.from(shot.data, "base64"));
  console.log("saved", out);
  ws.close();
}

main().catch((e) => { console.error(e); process.exit(1); });
