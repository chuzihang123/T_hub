"""Poll the battery command for 20s and report any non-zero answer."""

import ctypes
import sys
import time

sys.path.insert(0, r"D:\work\qd\poc")
import hid_probe as hp  # noqa: E402

hid = hp.hid
HidD_SetFeature = hid.HidD_SetFeature
HidD_SetFeature.argtypes = [hp.wt.HANDLE, ctypes.c_void_p, hp.wt.ULONG]
HidD_SetFeature.restype = hp.wt.BOOL


def send(h, rid, plen, body):
    body = bytes(body) + bytes(plen - len(body))
    size = 1 + plen
    buf = ctypes.create_string_buffer(size)
    buf[0] = bytes([rid])
    buf[1:size] = bytes(b ^ 0xFF for b in body)
    return bool(HidD_SetFeature(h, buf, size))


def get(h, rid, plen):
    size = 1 + plen
    buf = ctypes.create_string_buffer(size)
    buf[0] = bytes([rid])
    if hp.HidD_GetFeature(h, buf, size):
        raw = buf.raw
        return raw[1] ^ 0xFF, bytes(b ^ 0xFF for b in raw[2:])
    return None, b""


def main(seconds=20):
    handles = []
    for path in hp.enumerate_hid():
        h, err = hp.open_path(path)
        if h is None:
            continue
        attrs = hp.HIDD_ATTRIBUTES()
        attrs.Size = ctypes.sizeof(attrs)
        if not hp.HidD_GetAttributes(h, ctypes.byref(attrs)):
            hp.CloseHandle(h)
            continue
        caps = hp.caps_of(h)
        if caps is None or caps.UsagePage != 0xFF01:
            hp.CloseHandle(h)
            continue
        handles.append((h, f"{attrs.VendorID:04X}:{attrs.ProductID:04X}"))

    t0 = time.time()
    seen = {name: set() for _, name in handles}
    while time.time() - t0 < seconds:
        for h, name in handles:
            send(h, 0x11, 20, bytes([0x06]))
            _, d = get(h, 0x11, 20)
            if d and any(d[:12]) and d[:12] not in seen[name]:
                seen[name].add(d[:12])
                print(f"[{time.time()-t0:5.1f}s] {name} 0x06 -> {d[:12].hex(' ')}", flush=True)
        time.sleep(0.4)
    for name, s in seen.items():
        print(f"{name}: {len(s)} distinct non-zero responses", flush=True)
    for h, _ in handles:
        hp.CloseHandle(h)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20)
