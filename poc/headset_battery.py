"""Query the MCHOSE V9 PRO headset battery: output report 0x55 cmd 0x65."""

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
k32.CancelIoEx.argtypes = [wt.HANDLE, ctypes.c_void_p]
k32.GetOverlappedResult.argtypes = [wt.HANDLE, ctypes.c_void_p,
                                    ctypes.POINTER(wt.DWORD), wt.BOOL]


def test(path, out_len):
    h = k32.CreateFileW(path, GENERIC_READ | GENERIC_WRITE,
                        FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                        OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
    if h == INVALID:
        print("  open failed", ctypes.get_last_error())
        return
    try:
        ev_write = k32.CreateEventW(None, True, False, None)
        ev_read = k32.CreateEventW(None, True, False, None)

        # arm an async read first
        rbuf = ctypes.create_string_buffer(out_len)
        rov = OVERLAPPED()
        rov.hEvent = ev_read
        rd = wt.DWORD(0)
        k32.ReadFile(h, rbuf, out_len, ctypes.byref(rd), ctypes.byref(rov))

        # request: [0x55][0x65][0x01][0...]
        frame = bytes([0x55, 0x65, 0x01]) + bytes(out_len - 3)
        wbuf = ctypes.create_string_buffer(frame, out_len)
        wov = OVERLAPPED()
        wov.hEvent = ev_write
        wr = wt.DWORD(0)
        ok = k32.WriteFile(h, wbuf, out_len, ctypes.byref(wr), ctypes.byref(wov))
        if not ok and ctypes.get_last_error() != ERROR_IO_PENDING:
            print("  write failed", ctypes.get_last_error())
            return

        deadline = time.time() + 1.5
        got = []
        while time.time() < deadline:
            if k32.WaitForSingleObject(ev_read, 300) == 0:
                k32.GetOverlappedResult(h, ctypes.byref(rov), ctypes.byref(rd), False)
                got.append(rbuf.raw[: rd.value])
                # re-arm
                rbuf = ctypes.create_string_buffer(out_len)
                rov = OVERLAPPED()
                rov.hEvent = ev_read
                rd = wt.DWORD(0)
                k32.ReadFile(h, rbuf, out_len, ctypes.byref(rd), ctypes.byref(rov))
            else:
                break
        for g in got:
            print("  in:", g[:24].hex(" "))
        if not got:
            print("  no answer")
    finally:
        k32.CloseHandle(h)


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
        if not ok or not caps:
            continue
        if a.VendorID != 0x291D or a.ProductID != 0x385D:
            continue
        if caps.OutputReportByteLength != 64:
            continue
        print(f"== upage={caps.UsagePage:#06x} in={caps.InputReportByteLength} out={caps.OutputReportByteLength} feat={caps.FeatureReportByteLength}")
        test(path, caps.OutputReportByteLength)


if __name__ == "__main__":
    main()
