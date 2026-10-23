"""Probe VGN keyboards over HID.

VGN's VHUB ships a readable keyboard SDK, so the framing below is not a
guess: it is what the vendor's own code does.

  v2  three-mode info   request  [0x0D, 0x01, 0x00 ...]        (64 bytes)
      reply                     [0x0D, status, mode, charge, battery]
  v1  sync              request  [0x5C, 0x06, 0x01, 0x97, 0x01, 0x02, 0x03, 0x04, 0xFF, 0xFF]
      head 0x5C, len, cmd, crc;  crc = 0x35 + head + len + cmd + last data byte

Nothing here writes settings: only the two read commands above are sent.
The script also listens for a moment on every vendor collection, because
wireless keyboards broadcast their state frame on their own.

Run:  python poc\\vgn_probe.py
"""

import ctypes
import ctypes.wintypes as wt
import struct
import sys
import time
import uuid

hid = ctypes.WinDLL("hid.dll")
setupapi = ctypes.WinDLL("setupapi.dll")
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x01
FILE_SHARE_WRITE = 0x02
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
INVALID_HANDLE_VALUE = wt.HANDLE(-1).value
ERROR_NO_MORE_ITEMS = 259

# usage pages that carry the vendor channel
VENDOR_PAGES = {0xFFA0, 0xFFB0, 0xFF60, 0xFF02, 0xFF01}


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wt.DWORD),
        ("Data2", wt.WORD),
        ("Data3", wt.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_string(cls, s):
        g = cls()
        ctypes.memmove(ctypes.byref(g), uuid.UUID(s).bytes_le, 16)
        return g


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wt.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Size", wt.ULONG),
        ("VendorID", wt.USHORT),
        ("ProductID", wt.USHORT),
        ("VersionNumber", wt.USHORT),
    ]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wt.USHORT),
        ("UsagePage", wt.USHORT),
        ("InputReportByteLength", wt.USHORT),
        ("OutputReportByteLength", wt.USHORT),
        ("FeatureReportByteLength", wt.USHORT),
        ("Reserved", wt.USHORT * 17),
        ("NumberLinkCollectionNodes", wt.USHORT),
        ("NumberInputButtonCaps", wt.USHORT),
        ("NumberInputValueCaps", wt.USHORT),
        ("NumberInputDataIndices", wt.USHORT),
        ("NumberOutputButtonCaps", wt.USHORT),
        ("NumberOutputValueCaps", wt.USHORT),
        ("NumberOutputDataIndices", wt.USHORT),
        ("NumberFeatureButtonCaps", wt.USHORT),
        ("NumberFeatureValueCaps", wt.USHORT),
        ("NumberFeatureDataIndices", wt.USHORT),
    ]


class OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_size_t),
        ("InternalHigh", ctypes.c_size_t),
        ("Offset", wt.DWORD),
        ("OffsetHigh", wt.DWORD),
        ("hEvent", wt.HANDLE),
    ]


SetupDiGetClassDevsW = setupapi.SetupDiGetClassDevsW
SetupDiGetClassDevsW.restype = ctypes.c_void_p
SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wt.LPCWSTR, wt.HWND, wt.DWORD]

SetupDiEnumDeviceInterfaces = setupapi.SetupDiEnumDeviceInterfaces
SetupDiEnumDeviceInterfaces.restype = wt.BOOL
SetupDiEnumDeviceInterfaces.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID), wt.DWORD,
    ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
]

SetupDiGetDeviceInterfaceDetailW = setupapi.SetupDiGetDeviceInterfaceDetailW
SetupDiGetDeviceInterfaceDetailW.restype = wt.BOOL
SetupDiGetDeviceInterfaceDetailW.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), ctypes.c_void_p,
    wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p,
]

CreateFileW = kernel32.CreateFileW
CreateFileW.restype = wt.HANDLE
CreateFileW.argtypes = [
    wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE,
]

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wt.HANDLE]

ReadFile = kernel32.ReadFile
ReadFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD),
                     ctypes.POINTER(OVERLAPPED)]

WriteFile = kernel32.WriteFile
WriteFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD),
                      ctypes.POINTER(OVERLAPPED)]

WaitForSingleObject = kernel32.WaitForSingleObject
WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]

GetOverlappedResult = kernel32.GetOverlappedResult
GetOverlappedResult.argtypes = [wt.HANDLE, ctypes.POINTER(OVERLAPPED),
                                ctypes.POINTER(wt.DWORD), wt.BOOL]

CreateEventW = kernel32.CreateEventW
CreateEventW.restype = wt.HANDLE
CreateEventW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.BOOL, wt.LPCWSTR]

HidD_GetAttributes = hid.HidD_GetAttributes
HidD_GetAttributes.argtypes = [wt.HANDLE, ctypes.POINTER(HIDD_ATTRIBUTES)]

HidD_GetPreparsedData = hid.HidD_GetPreparsedData
HidD_GetPreparsedData.argtypes = [wt.HANDLE, ctypes.POINTER(ctypes.c_void_p)]

HidD_FreePreparsedData = hid.HidD_FreePreparsedData
HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]

HidP_GetCaps = hid.HidP_GetCaps
HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]

HidD_GetProductString = hid.HidD_GetProductString
HidD_GetProductString.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]

HidD_GetManufacturerString = hid.HidD_GetManufacturerString
HidD_GetManufacturerString.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]


def enumerate_hid():
    guid = GUID.from_string("{4D1E55B2-F16F-11CF-88CB-001111000030}")
    hdev = SetupDiGetClassDevsW(ctypes.byref(guid), None, None,
                                DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if hdev == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        idx = 0
        while True:
            did = SP_DEVICE_INTERFACE_DATA()
            did.cbSize = ctypes.sizeof(did)
            if not SetupDiEnumDeviceInterfaces(hdev, None, ctypes.byref(guid), idx,
                                               ctypes.byref(did)):
                err = ctypes.get_last_error()
                if err in (0, ERROR_NO_MORE_ITEMS):
                    return
                raise ctypes.WinError(err)
            idx += 1
            need = wt.DWORD(0)
            SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(did), None, 0,
                                             ctypes.byref(need), None)
            buf = ctypes.create_string_buffer(need.value)
            ctypes.c_uint32.from_buffer(buf).value = (
                8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6)
            if not SetupDiGetDeviceInterfaceDetailW(
                    hdev, ctypes.byref(did), buf, need.value, ctypes.byref(need), None):
                raise ctypes.WinError(ctypes.get_last_error())
            yield ctypes.wstring_at(ctypes.addressof(buf) + 4)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(ctypes.c_void_p(hdev))


def open_path(path, overlapped=False):
    flags = FILE_FLAG_OVERLAPPED if overlapped else 0
    h = CreateFileW(path, GENERIC_READ | GENERIC_WRITE,
                    FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, flags, None)
    if h == INVALID_HANDLE_VALUE:
        return None
    return h


def caps_of(h):
    preparsed = ctypes.c_void_p()
    if not HidD_GetPreparsedData(h, ctypes.byref(preparsed)):
        return None
    try:
        caps = HIDP_CAPS()
        if HidP_GetCaps(preparsed, ctypes.byref(caps)) != 0x00110000:
            return None
        return caps
    finally:
        HidD_FreePreparsedData(preparsed)


def wstring(fn, h):
    buf = ctypes.create_unicode_buffer(256)
    if fn(h, buf, ctypes.sizeof(buf)):
        return buf.value
    return ""


def exchange(name, path, payload, listen_ms=0, wait_ms=500):
    """Write one 64-byte vendor frame and return whatever comes back."""
    h = open_path(path, overlapped=True)
    if h is None:
        print("    open failed (%s)" % name)
        return None
    rev = wev = None
    try:
        inbuf = ctypes.create_string_buffer(66)
        ro = OVERLAPPED()
        rev = CreateEventW(None, True, False, None)
        ro.hEvent = rev
        got = wt.DWORD(0)
        ReadFile(h, inbuf, 66, ctypes.byref(got), ctypes.byref(ro))

        if listen_ms:
            if WaitForSingleObject(rev, listen_ms) == 0:
                GetOverlappedResult(h, ctypes.byref(ro), ctypes.byref(got), False)
                data = inbuf.raw[:got.value]
                print("    broadcast %-3d  %s" % (len(data), data.hex(" ")))
                inbuf = ctypes.create_string_buffer(66)
                ro = OVERLAPPED()
                rev = CreateEventW(None, True, False, None)
                ro.hEvent = rev
                ReadFile(h, inbuf, 66, ctypes.byref(got), ctypes.byref(ro))

        out = bytearray(65)
        out[0] = 0x00
        out[1:1 + len(payload)] = payload
        cbuf = (ctypes.c_char * len(out)).from_buffer(out)
        wo = OVERLAPPED()
        wev = CreateEventW(None, True, False, None)
        wo.hEvent = wev
        wrote = wt.DWORD(0)
        ok = WriteFile(h, cbuf, len(out), ctypes.byref(wrote), ctypes.byref(wo))
        if not ok and ctypes.get_last_error() != 997:  # 997 = still pending
            print("    %-9s write failed, err=%d" % (name, ctypes.get_last_error()))
            return None
        WaitForSingleObject(wev, 300)

        if WaitForSingleObject(rev, wait_ms) != 0:
            print("    %-9s no reply" % name)
            return None
        GetOverlappedResult(h, ctypes.byref(ro), ctypes.byref(got), False)
        if got.value == 0:
            print("    %-9s empty reply" % name)
            return None
        data = inbuf.raw[:got.value]
        print("    %-9s reply %-3d  %s" % (name, len(data), data.hex(" ")))
        return data
    finally:
        if rev:
            CloseHandle(rev)
        if wev:
            CloseHandle(wev)
        CloseHandle(h)


def describe(name, path):
    h = open_path(path)
    if h is None:
        return None
    try:
        attrs = HIDD_ATTRIBUTES()
        attrs.Size = ctypes.sizeof(attrs)
        if not HidD_GetAttributes(h, ctypes.byref(attrs)):
            return None
        caps = caps_of(h)
        if caps is None:
            return None
        info = {
            "path": path,
            "vid": attrs.VendorID,
            "pid": attrs.ProductID,
            "usage": caps.Usage,
            "usage_page": caps.UsagePage,
            "in_len": caps.InputReportByteLength,
            "out_len": caps.OutputReportByteLength,
            "feat_len": caps.FeatureReportByteLength,
            "product": wstring(HidD_GetProductString, h),
            "manufacturer": wstring(HidD_GetManufacturerString, h),
        }
        return info
    finally:
        CloseHandle(h)


def parse_v2(data):
    # report id 0 is stripped into byte 0 by the HID stack, so the frame
    # may start at either offset
    off = 1 if len(data) > 5 and data[1] == 0x0D else 0
    if len(data) < off + 5 or data[off] != 0x0D:
        return None
    status, mode, charge, battery = data[off + 1:off + 5]
    return {"status": status, "mode": mode, "charge": charge, "battery": battery}


def main():
    print("HID vendor collections\n" + "-" * 72)
    candidates = []
    for path in enumerate_hid():
        info = describe("", path)
        if info is None:
            continue
        if info["usage_page"] < 0xFF00:
            continue
        tag = ""
        if info["vid"] in (0x25AA, 0x1CA3) or "VGN" in info["product"].upper() \
                or "VXE" in info["product"].upper():
            tag = "  <-- looks like VGN"
        print("%04X:%04X  page=%#06x usage=%#06x  in=%d out=%d feat=%d  %r%s" % (
            info["vid"], info["pid"], info["usage_page"], info["usage"],
            info["in_len"], info["out_len"], info["feat_len"],
            info["product"], tag))
        if info["manufacturer"]:
            print("            manufacturer=%r" % info["manufacturer"])
        if info["usage"] == 1 and info["usage_page"] in VENDOR_PAGES:
            candidates.append(info)

    if not candidates:
        print("\n没有找到可用的厂商集合。键盘是不是没连上？")
        return

    print("\nprobe\n" + "-" * 72)
    for info in candidates:
        print("\n%04X:%04X page=%#06x %r" % (
            info["vid"], info["pid"], info["usage_page"], info["product"]))
        listen = 300
        data = exchange("v2 0D01", info["path"], bytes([0x0D, 0x01]), listen_ms=listen)
        parsed = parse_v2(data) if data else None
        if parsed:
            print("    -> %s" % parsed)
            if parsed["status"] == 0 and 0 < parsed["battery"] <= 100:
                print("    -> 电量 %d%%  充电=%d  模式=%d"
                      % (parsed["battery"], parsed["charge"], parsed["mode"]))
            continue
        # v1 fallback: head 0x5C, len 6, cmd 0x01, crc, + sync payload
        payload = bytes([0x5C, 0x06, 0x01, 0x97, 0x01, 0x02, 0x03, 0x04, 0xFF, 0xFF])
        data = exchange("v1 sync", info["path"], payload)
        if data:
            print("    -> v1 有回包，帧头 %s" % data[:6].hex(" "))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print("failed: %s" % exc)
        sys.exit(1)
