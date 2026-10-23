"""Passively listen to the generic 2.4G keyboard vendor collections."""

import ctypes
import sys
import time
from ctypes import wintypes as wt

sys.path.insert(0, r"D:\work\qd\poc")
import hid_probe as hp  # noqa: E402

k32 = hp.kernel32
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
INVALID = wt.HANDLE(-1).value
ERROR_IO_PENDING = 997


class OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_void_p),
        ("InternalHigh", ctypes.c_void_p),
        ("Offset", wt.DWORD),
        ("OffsetHigh", wt.DWORD),
        ("hEvent", wt.HANDLE),
    ]


k32.CreateEventW.restype = wt.HANDLE
k32.CreateEventW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.BOOL, wt.LPCWSTR]
k32.ReadFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD,
                         ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
k32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
k32.CancelIoEx.argtypes = [wt.HANDLE, ctypes.c_void_p]
k32.GetOverlappedResult.argtypes = [wt.HANDLE, ctypes.c_void_p,
                                    ctypes.POINTER(wt.DWORD), wt.BOOL]


def listen(path, seconds):
    h = k32.CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                        None, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
    if h == INVALID:
        print(f"  open failed err={ctypes.get_last_error()}")
        return
    try:
        caps = hp.caps_of(h)
        n = caps.InputReportByteLength
        print(f"  upage={caps.UsagePage:#06x} usage={caps.Usage:#06x} inlen={n}")
        ev = k32.CreateEventW(None, True, False, None)
        seen = {}
        t0 = time.time()
        while time.time() - t0 < seconds:
            buf = ctypes.create_string_buffer(n)
            ov = OVERLAPPED()
            ov.hEvent = ev
            rd = wt.DWORD(0)
            ok = k32.ReadFile(h, buf, n, ctypes.byref(rd), ctypes.byref(ov))
            if not ok:
                err = ctypes.get_last_error()
                if err != ERROR_IO_PENDING:
                    print(f"  read err={err}")
                    break
            if k32.WaitForSingleObject(ev, 300) == 0:
                k32.GetOverlappedResult(h, ctypes.byref(ov), ctypes.byref(rd), False)
                data = buf.raw[: rd.value]
                seen[data] = seen.get(data, 0) + 1
            else:
                k32.CancelIoEx(h, ctypes.byref(ov))
        for d, c in sorted(seen.items(), key=lambda x: -x[1])[:15]:
            print(f"  x{c:<3} {d.hex(' ')}")
        if not seen:
            print("  (no reports)")
    finally:
        k32.CloseHandle(h)


def main():
    targets = []
    for path in hp.enumerate_hid():
        h, e = hp.open_path(path)
        if not h:
            continue
        a = hp.HIDD_ATTRIBUTES()
        a.Size = ctypes.sizeof(a)
        ok = hp.HidD_GetAttributes(h, ctypes.byref(a))
        caps = hp.caps_of(h) if ok else None
        hp.CloseHandle(h)
        if ok and caps and a.VendorID == 0x1A2C and a.ProductID == 0x8FFF:
            targets.append((caps.UsagePage, path))
    for page, path in sorted(targets):
        print(f"== upage={page:#06x}")
        listen(path, 15)


if __name__ == "__main__":
    main()
