"""Figure out the 0x11 short-command transport: set-then-get variants."""

import ctypes
import ctypes.wintypes as wt
import struct
import sys

sys.path.insert(0, r"D:\work\qd\poc")

import hid_probe as hp  # noqa: E402

hid = hp.hid

HidD_SetFeature = hid.HidD_SetFeature
HidD_SetFeature.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]
HidD_SetFeature.restype = wt.BOOL


def frame(cmd, payload_len, args=b""):
    body = bytes([cmd]) + args + bytes([0x00] * (payload_len - 1 - len(args)))
    return bytes(b ^ 0xFF for b in body)


def set_and_get(h, rid, plen, cmd, args=b"", get_len=None):
    size = 1 + plen
    buf = ctypes.create_string_buffer(size)
    buf[0] = bytes([rid])
    buf[1:size] = frame(cmd, plen, args)
    ok_set = bool(HidD_SetFeature(h, buf, size))
    err = ctypes.get_last_error()

    glen = get_len or size
    rbuf = ctypes.create_string_buffer(glen)
    rbuf[0] = bytes([rid])
    ok_get = bool(hp.HidD_GetFeature(h, rbuf, glen))
    gerr = ctypes.get_last_error()
    raw = rbuf.raw
    return ok_set, err, ok_get, gerr, raw


def try_variant(h, label, rid, plen, cmd, args=b"", get_len=None):
    ok_set, err, ok_get, gerr, raw = set_and_get(h, rid, plen, cmd, args, get_len)
    echo = raw[1] ^ 0xFF if len(raw) > 1 else None
    data = bytes(b ^ 0xFF for b in raw[2:]) if len(raw) > 2 else b""
    print(f"  {label}: set={ok_set}/err{err} get={ok_get}/err{gerr} "
          f"rid={raw[0]:#04x} echo={echo if echo is None else hex(echo)} data={data[:16].hex()}")
    return ok_get and echo == cmd, data


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
            print(f"\n=== {attrs.VendorID:04X}:{attrs.ProductID:04X} feat={caps.FeatureReportByteLength}")
            for get_len in (21, 65):
                try_variant(h, f"0x06 getlen={get_len}", 0x11, 20, 0x06, get_len=get_len)
            for get_len in (21, 65):
                try_variant(h, f"0x03 getlen={get_len}", 0x11, 20, 0x03, get_len=get_len)
            try_variant(h, "0x04 getlen=21", 0x11, 20, 0x04, get_len=21)

            ok, data = try_variant(h, "0x06 verbose", 0x11, 20, 0x06, get_len=21)
            if data:
                print("    raw bytes:", data[:12].hex(" "))
        finally:
            hp.CloseHandle(h)


if __name__ == "__main__":
    main()
