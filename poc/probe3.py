"""Ordered probe: 0x03 -> 0x06 -> 0x58(profile 0) -> 0x67 -> 0x06 again."""

import ctypes
import struct
import sys

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


def cmd(h, rid, plen, c, args=b""):
    body = bytes([c]) + args + bytes([0] * (plen - 1 - len(args)))
    send(h, rid, plen, body)
    echo, data = get(h, rid, plen)
    return echo, data


def main():
    for path in hp.enumerate_hid():
        h, err = hp.open_path(path)
        if h is None:
            continue
        try:
            attrs = hp.HIDD_ATTRIBUTES()
            attrs.Size = ctypes.sizeof(attrs)
            if not hp.HidD_GetAttributes(h, ctypes.byref(attrs)):
                continue
            caps = hp.caps_of(h)
            if caps is None or caps.UsagePage != 0xFF01:
                continue
            name = f"{attrs.VendorID:04X}:{attrs.ProductID:04X}"
            print(f"\n=== {name}")

            e, d = cmd(h, 0x11, 20, 0x03)
            print(f"  0x03 -> {d[:9].hex(' ')}")
            e, d = cmd(h, 0x11, 20, 0x06)
            print(f"  0x06 -> {d[:12].hex(' ')}")

            # re-select profile 0 through the short channel (documented unwedge)
            print(f"  0x58(0) set -> {send(h, 0x11, 20, bytes([0x58, 0]))}")
            e, d = cmd(h, 0x12, 64, 0x67)
            print(f"  0x67 -> {d[:16].hex(' ') if d else 'none'}")

            e, d = cmd(h, 0x11, 20, 0x06)
            print(f"  0x06 again -> {d[:12].hex(' ')}")
        finally:
            hp.CloseHandle(h)


if __name__ == "__main__":
    main()
