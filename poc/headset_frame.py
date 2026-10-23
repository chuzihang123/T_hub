"""MCHOSE V9 PRO battery via templated frame: AA 01 00 01 00 01 0B 00 ..."""

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


def build_frame(cmd=0x0B, cmd_type=(0x00, 0x01), payload=(), total=63):
    frame = bytearray(total)
    frame[0] = 0xAA
    frame[1] = 0x01
    frame[2] = 0x00            # flags
    frame[3] = len(payload) + 1
    frame[4] = cmd_type[0]
    frame[5] = cmd_type[1]
    frame[6] = cmd
    frame[7:7 + len(payload)] = bytes(payload)
    # checksum is 0 when the check flag is clear
    return bytes(frame)


def query(path, out_len, frame):
    h = k32.CreateFileW(path, GENERIC_READ | GENERIC_WRITE,
                        FILE_SHARE_READ | FILE_SHARE_WRITE, None,
                        OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
    if h == INVALID:
        print("  open failed", ctypes.get_last_error())
        return
    try:
        ev_r = k32.CreateEventW(None, True, False, None)
        ev_w = k32.CreateEventW(None, True, False, None)

        rbuf = ctypes.create_string_buffer(out_len)
        rov = OVERLAPPED(); rov.hEvent = ev_r
        rd = wt.DWORD(0)
        k32.ReadFile(h, rbuf, out_len, ctypes.byref(rd), ctypes.byref(rov))

        data = bytes([0x55]) + frame
        wbuf = ctypes.create_string_buffer(data, len(data))
        wov = OVERLAPPED(); wov.hEvent = ev_w
        wr = wt.DWORD(0)
        ok = k32.WriteFile(h, wbuf, len(data), ctypes.byref(wr), ctypes.byref(wov))
        err = ctypes.get_last_error()
        print(f"  write ok={ok} err={err} len={len(data)}")

        deadline = time.time() + 2.0
        while time.time() < deadline:
            if k32.WaitForSingleObject(ev_r, 300) == 0:
                k32.GetOverlappedResult(h, ctypes.byref(rov), ctypes.byref(rd), False)
                d = rbuf.raw[:rd.value]
                print("  in:", d[:20].hex(" "))
                if len(d) > 7 and d[4:7] == b"\x00\x01\x0b":
                    payload = d[7:7 + d[3]]
                    print("  payload:", payload.hex(" "),
                          "-> percent", payload[1] & 0x7F,
                          "charging", bool(payload[1] & 0x80))
                rbuf = ctypes.create_string_buffer(out_len)
                rov = OVERLAPPED(); rov.hEvent = ev_r
                rd = wt.DWORD(0)
                k32.ReadFile(h, rbuf, out_len, ctypes.byref(rd), ctypes.byref(rov))
            else:
                break
    finally:
        k32.CloseHandle(h)


def main():
    frame = build_frame()
    print("frame:", frame[:10].hex(" "))
    for path in hp.enumerate_hid():
        h, e = hp.open_path(path)
        if not h:
            continue
        a = hp.HIDD_ATTRIBUTES(); a.Size = ctypes.sizeof(a)
        ok = hp.HidD_GetAttributes(h, ctypes.byref(a))
        caps = hp.caps_of(h) if ok else None
        hp.CloseHandle(h)
        if not ok or not caps:
            continue
        if a.VendorID != 0x291D or a.ProductID != 0x385D:
            continue
        if caps.OutputReportByteLength != 64:
            continue
        print(f"== upage={caps.UsagePage:#06x}")
        query(path, caps.InputReportByteLength or 64, frame)


if __name__ == "__main__":
    main()
