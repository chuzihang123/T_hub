"""Send a feature-report command, then listen on input reports for the answer."""

import ctypes
import sys
import time
from ctypes import wintypes as wt

sys.path.insert(0, r"D:\work\qd\poc")
import hid_probe as hp  # noqa: E402

k32 = hp.kernel32
hid = hp.hid
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
INVALID = wt.HANDLE(-1).value
ERROR_IO_PENDING = 997


class OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_void_p), ("InternalHigh", ctypes.c_void_p),
        ("Offset", wt.DWORD), ("OffsetHigh", wt.DWORD), ("hEvent", wt.HANDLE),
    ]


k32.CreateEventW.restype = wt.HANDLE
k32.CreateEventW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.BOOL, wt.LPCWSTR]
k32.ReadFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD,
                         ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
k32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
k32.CancelIoEx.argtypes = [wt.HANDLE, ctypes.c_void_p]
k32.GetOverlappedResult.argtypes = [wt.HANDLE, ctypes.c_void_p,
                                    ctypes.POINTER(wt.DWORD), wt.BOOL]

SetFeature = hid.HidD_SetFeature
SetFeature.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]
SetFeature.restype = wt.BOOL


def pump(h, seconds, label):
    caps = hp.caps_of(h)
    n = caps.InputReportByteLength
    ev = k32.CreateEventW(None, True, False, None)
    seen = {}
    t0 = time.time()
    while time.time() - t0 < seconds:
        buf = ctypes.create_string_buffer(n)
        ov = OVERLAPPED()
        ov.hEvent = ev
        rd = wt.DWORD(0)
        if not k32.ReadFile(h, buf, n, ctypes.byref(rd), ctypes.byref(ov)):
            if ctypes.get_last_error() != ERROR_IO_PENDING:
                break
        if k32.WaitForSingleObject(ev, 200) == 0:
            k32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(rd), False)
            d = buf.raw[: rd.value]
            seen[d] = seen.get(d, 0) + 1
        else:
            k32.CancelIoEx(h, ctypes.byref(ov))
    for d, c in seen.items():
        print(f"    {label} input x{c}: {d.hex(' ')}")
    if not seen:
        print(f"    {label}: no input report")


def main():
    for path in hp.enumerate_hid():
        h, e = hp.open_path(path)
        if not h:
            continue
        a = hp.HIDD_ATTRIBUTES()
        a.Size = ctypes.sizeof(a)
        ok = hp.HidD_GetAttributes(h, ctypes.byref(a))
        caps = hp.caps_of(h) if ok else None
        hp.CloseHandle(h)
        if not (ok and caps and caps.UsagePage == 0xFF01
                and a.VendorID in (0x3837, 0x5253)):
            continue

        print(f"\n== {a.VendorID:04X}:{a.ProductID:04X}")
        rw = k32.CreateFileW(path, GENERIC_READ | GENERIC_WRITE,
                             FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                             OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
        if rw == INVALID:
            print("  open failed", ctypes.get_last_error())
            continue
        try:
            for rid, plen, cmd in ((0x11, 20, 0x06), (0x11, 20, 0x03), (0x12, 64, 0x67)):
                body = bytes([cmd]) + bytes(plen - 1)
                b = ctypes.create_string_buffer(1 + plen)
                b[0] = bytes([rid])
                b[1:] = bytes(x ^ 0xFF for x in body)
                ok = bool(SetFeature(rw, b, 1 + plen))
                print(f"  set cmd={cmd:#04x} ok={ok}")
                pump(rw, 0.6, f"cmd{cmd:#04x}")
        finally:
            k32.CloseHandle(rw)


if __name__ == "__main__":
    main()
