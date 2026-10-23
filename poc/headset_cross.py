"""Write the battery query on 0xFF90 while listening on every headset collection."""

import ctypes
import sys
import time
from ctypes import wintypes as wt

sys.path.insert(0, r"D:\work\qd\poc")
import hid_probe as hp  # noqa: E402

k32 = hp.kernel32
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
k32.WriteFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD,
                          ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
k32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
k32.GetOverlappedResult.argtypes = [wt.HANDLE, ctypes.c_void_p,
                                    ctypes.POINTER(wt.DWORD), wt.BOOL]


def main():
    frame = bytearray(63)
    frame[0] = 0xAA; frame[1] = 0x01; frame[2] = 0x00
    frame[3] = 0x01; frame[4] = 0x00; frame[5] = 0x01; frame[6] = 0x0B

    readers = []
    writer = None
    writer_len = 0
    for path in hp.enumerate_hid():
        h, e = hp.open_path(path)
        if not h:
            continue
        a = hp.HIDD_ATTRIBUTES(); a.Size = ctypes.sizeof(a)
        ok = hp.HidD_GetAttributes(h, ctypes.byref(a))
        caps = hp.caps_of(h) if ok else None
        hp.CloseHandle(h)
        if not ok or not caps or a.VendorID != 0x291D:
            continue
        if caps.InputReportByteLength >= 2:
            rh = k32.CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                                 None, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
            if rh != INVALID:
                n = caps.InputReportByteLength
                buf = ctypes.create_string_buffer(n)
                ev = k32.CreateEventW(None, True, False, None)
                ov = OVERLAPPED(); ov.hEvent = ev
                rd = wt.DWORD(0)
                k32.ReadFile(rh, buf, n, ctypes.byref(rd), ctypes.byref(ov))
                readers.append((caps.UsagePage, rh, n, buf, ev, ov, rd))
        if caps.OutputReportByteLength == 64 and writer is None:
            wh = k32.CreateFileW(path, GENERIC_READ | GENERIC_WRITE,
                                 FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                                 OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
            if wh != INVALID:
                writer = wh
                writer_len = caps.OutputReportByteLength
                writer_page = caps.UsagePage

    print("readers:", [(hex(p), n) for p, _, n, *_ in readers], "writer page:", hex(writer_page) if writer else None)
    if not writer:
        return
    data = bytes([0x55]) + bytes(frame)
    wbuf = ctypes.create_string_buffer(data, len(data))
    ev_w = k32.CreateEventW(None, True, False, None)
    wov = OVERLAPPED(); wov.hEvent = ev_w
    wr = wt.DWORD(0)
    if not k32.WriteFile(writer, wbuf, len(data), ctypes.byref(wr), ctypes.byref(wov)):
        if ctypes.get_last_error() != ERROR_IO_PENDING:
            print("write failed", ctypes.get_last_error())
    k32.WaitForSingleObject(ev_w, 1000)

    deadline = time.time() + 3.0
    while time.time() < deadline:
        for idx, (page, rh, n, buf, ev, ov, rd) in enumerate(readers):
            if k32.WaitForSingleObject(ev, 0) == 0:
                k32.GetOverlappedResult(rh, ctypes.byref(ov), ctypes.byref(rd), False)
                print(f"  [{page:#06x}] {buf.raw[:rd.value].hex(' ')}")
                nb = ctypes.create_string_buffer(n)
                nev = k32.CreateEventW(None, True, False, None)
                nov = OVERLAPPED(); nov.hEvent = nev
                nrd = wt.DWORD(0)
                k32.ReadFile(rh, nb, n, ctypes.byref(nrd), ctypes.byref(nov))
                readers[idx] = (page, rh, n, nb, nev, nov, nrd)
        time.sleep(0.05)


if __name__ == "__main__":
    main()
