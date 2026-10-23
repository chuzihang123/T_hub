"""Passively listen to VGN dongle HID input reports."""

import ctypes
import sys
import time
from ctypes import wintypes as wt

sys.path.insert(0, r"D:\work\qd\poc")
import hid_probe as hp  # noqa: E402

k32 = hp.kernel32
GR = 0x80000000
SHARE = 3
OPEN = 3
OV = 0x40000000
INVALID = wt.HANDLE(-1).value


class OVER(ctypes.Structure):
    _fields_ = [("Internal", ctypes.c_void_p), ("InternalHigh", ctypes.c_void_p),
                ("Offset", wt.DWORD), ("OffsetHigh", wt.DWORD), ("hEvent", wt.HANDLE)]


k32.CreateEventW.restype = wt.HANDLE
k32.CreateEventW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.BOOL, wt.LPCWSTR]
k32.ReadFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD,
                         ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
k32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
k32.GetOverlappedResult.argtypes = [wt.HANDLE, ctypes.c_void_p,
                                    ctypes.POINTER(wt.DWORD), wt.BOOL]

readers = []
for path in hp.enumerate_hid():
    h = None
    try:
        h, e = hp.open_path(path)
        if not h:
            continue
        a = hp.HIDD_ATTRIBUTES(); a.Size = ctypes.sizeof(a)
        if not hp.HidD_GetAttributes(h, ctypes.byref(a)):
            continue
        caps = hp.caps_of(h)
        if a.VendorID != 0x320F or caps.InputReportByteLength < 2:
            continue
        rh = k32.CreateFileW(path, GR, SHARE, None, OPEN, OV, None)
        if rh == INVALID:
            continue
        n = caps.InputReportByteLength
        buf = ctypes.create_string_buffer(n)
        ev = k32.CreateEventW(None, True, False, None)
        ov = OVER(); ov.hEvent = ev
        rd = wt.DWORD(0)
        k32.ReadFile(rh, buf, n, ctypes.byref(rd), ctypes.byref(ov))
        readers.append((caps.UsagePage, rh, n, buf, ev, ov, rd))
        print(f"armed upage={caps.UsagePage:#06x} len={n}", flush=True)
    except Exception:
        pass
    finally:
        if h:
            hp.CloseHandle(h)

print("listening 20s ...", flush=True)
deadline = time.time() + 20
seen = set()
while time.time() < deadline:
    for i, (page, rh, n, buf, ev, ov, rd) in enumerate(readers):
        if k32.WaitForSingleObject(ev, 30) == 0:
            k32.GetOverlappedResult(rh, ctypes.byref(ov), ctypes.byref(rd), False)
            d = buf.raw[:rd.value]
            key = (page, d)
            if d and key not in seen:
                seen.add(key)
                print(f"[{page:#06x}] {d.hex(' ')}", flush=True)
            nb = ctypes.create_string_buffer(n)
            nev = k32.CreateEventW(None, True, False, None)
            nov = OVER(); nov.hEvent = nev
            nrd = wt.DWORD(0)
            k32.ReadFile(rh, nb, n, ctypes.byref(nrd), ctypes.byref(nov))
            readers[i] = (page, rh, n, nb, nev, nov, nrd)

for r in readers:
    k32.CloseHandle(r[1])
print("done", flush=True)
