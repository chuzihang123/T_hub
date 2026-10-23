"""Probe MCHOSE vendor HID collections and read battery / info / config.

Read-only: only sends the documented read commands (0x11 0x03, 0x11 0x06,
0x11 0x04, 0x12 0x67). No writes, so it cannot change the mouse.
"""

import ctypes
import ctypes.wintypes as wt
import struct
import sys
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
INVALID_HANDLE_VALUE = wt.HANDLE(-1).value
ERROR_NO_MORE_ITEMS = 259


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wt.DWORD),
        ("Data2", wt.WORD),
        ("Data3", wt.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_string(cls, s):
        b = uuid.UUID(s).bytes_le
        g = cls()
        ctypes.memmove(ctypes.byref(g), b, 16)
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

HidD_GetAttributes = hid.HidD_GetAttributes
HidD_GetAttributes.argtypes = [wt.HANDLE, ctypes.POINTER(HIDD_ATTRIBUTES)]

HidD_GetPreparsedData = hid.HidD_GetPreparsedData
HidD_GetPreparsedData.argtypes = [wt.HANDLE, ctypes.POINTER(ctypes.c_void_p)]

HidD_FreePreparsedData = hid.HidD_FreePreparsedData
HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]

HidP_GetCaps = hid.HidP_GetCaps
HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]

HidD_GetFeature = hid.HidD_GetFeature
HidD_GetFeature.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]
HidD_GetFeature.restype = wt.BOOL

HidD_GetProductString = hid.HidD_GetProductString
HidD_GetProductString.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]


def enumerate_hid():
    guid = GUID.from_string("{4D1E55B2-F16F-11CF-88CB-001111000030}")
    flags = DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
    hdev = SetupDiGetClassDevsW(ctypes.byref(guid), None, None, flags)
    if hdev == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        idx = 0
        while True:
            did = SP_DEVICE_INTERFACE_DATA()
            did.cbSize = ctypes.sizeof(did)
            if not SetupDiEnumDeviceInterfaces(hdev, None, ctypes.byref(guid), idx, ctypes.byref(did)):
                err = ctypes.get_last_error()
                # setupapi was loaded without use_last_error, so a clean
                # end-of-list often reports 0 instead of ERROR_NO_MORE_ITEMS
                if err in (0, ERROR_NO_MORE_ITEMS):
                    return
                # some interfaces refuse access mid-enumeration; skip them
                idx += 1
                if idx > 400:
                    return
                continue
                raise ctypes.WinError(err)
            idx += 1
            need = wt.DWORD(0)
            SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(did), None, 0, ctypes.byref(need), None)
            buf = ctypes.create_string_buffer(need.value)
            ctypes.c_uint32.from_buffer(buf).value = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            if not SetupDiGetDeviceInterfaceDetailW(
                hdev, ctypes.byref(did), buf, need.value, ctypes.byref(need), None
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            yield ctypes.wstring_at(ctypes.addressof(buf) + 4)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(ctypes.c_void_p(hdev))


def open_path(path):
    h = CreateFileW(
        path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if h == INVALID_HANDLE_VALUE:
        return None, ctypes.get_last_error()
    return h, 0


def caps_of(h):
    preparsed = ctypes.c_void_p()
    if not HidD_GetPreparsedData(h, ctypes.byref(preparsed)):
        return None
    try:
        caps = HIDP_CAPS()
        if HidP_GetCaps(preparsed, ctypes.byref(caps)) != 0x00110000:  # HIDP_STATUS_SUCCESS
            return None
        return caps
    finally:
        HidD_FreePreparsedData(preparsed)


def read_feature(h, report_id, payload_len):
    """Send one read command and return (report_id, echoed_cmd, payload_bytes)."""
    size = 1 + payload_len
    req = ctypes.create_string_buffer(size)
    req[0] = bytes([report_id])
    body = bytes([0x00] * payload_len)
    req[1:size] = bytes(b ^ 0xFF for b in body)
    for _ in range(6):
        buf = ctypes.create_string_buffer(size)
        buf[0] = bytes([report_id])
        if HidD_GetFeature(h, buf, size):
            raw = buf.raw
            rid = raw[0]
            echo = raw[1] ^ 0xFF
            data = bytes(b ^ 0xFF for b in raw[2:])
            if rid == report_id:
                return rid, echo, data
    return None


def send_read(h, report_id, payload_len, cmd):
    size = 1 + payload_len
    req = ctypes.create_string_buffer(size)
    req[0] = bytes([report_id])
    body = bytes([cmd]) + bytes([0x00] * (payload_len - 1))
    req[1:size] = bytes(b ^ 0xFF for b in body)
    for _ in range(6):
        buf = ctypes.create_string_buffer(size)
        buf[0] = bytes([report_id])
        if HidD_GetFeature(h, buf, size):
            raw = buf.raw
            if raw[0] == report_id and (raw[1] ^ 0xFF) == cmd:
                return bytes(b ^ 0xFF for b in raw[2:])
    return None


VENDOR_PAGES = (0xFF01, 0xFF0B)
VENDOR_VIDS = {0x5253, 0x3837, 0x20DD, 0x1A2C, 0x291D, 0x0416, 0x0B05}


def main():
    found = 0
    for path in enumerate_hid():
        h, err = open_path(path)
        if h is None:
            continue
        try:
            attrs = HIDD_ATTRIBUTES()
            attrs.Size = ctypes.sizeof(attrs)
            if not HidD_GetAttributes(h, ctypes.byref(attrs)):
                continue
            caps = caps_of(h)
            if caps is None:
                continue
            if caps.UsagePage not in VENDOR_PAGES:
                continue
            if caps.FeatureReportByteLength < 21:
                continue
            found += 1
            prod = ctypes.create_unicode_buffer(256)
            HidD_GetProductString(h, prod, ctypes.sizeof(prod))
            print(f"\n=== {attrs.VendorID:04X}:{attrs.ProductID:04X}  upage={caps.UsagePage:#06x} "
                  f"usage={caps.Usage:#06x} feat={caps.FeatureReportByteLength}")
            print(f"    path={path}")
            print(f"    product={prod.value!r}")

            info = send_read(h, 0x11, 20, 0x03)
            if info:
                bond, vid, pid, connect, game = struct.unpack_from("<BHHBB", info)
                print(f"    0x03: bond={bond} vid={vid:04X} pid={pid:04X} connect={connect} game={game}")

            ver = send_read(h, 0x11, 20, 0x04)
            if ver:
                n = ver[0]
                print(f"    0x04: version={ver[1:1+n].decode('ascii', 'replace')!r}")

            st = send_read(h, 0x11, 20, 0x06)
            if st:
                vid, pid, fw, bits, batt, charge = struct.unpack_from("<HHIBBB", st)
                print(f"    0x06: vid={vid:04X} pid={pid:04X} fw=0x{fw:08X} "
                      f"connectMode={(bits >> 3) & 1} connectStatus={(bits >> 1) & 1} "
                      f"battery={batt}% charge={charge}")
            else:
                print("    0x06: no answer")

            cfg = send_read(h, 0x12, 64, 0x67)
            if cfg:
                n = cfg[0]
                print(f"    0x67: profileIndex={n} first16={cfg[:16].hex()}")
            else:
                print("    0x67: no answer")
        finally:
            CloseHandle(h)
    print(f"\nscanned vendor collections: {found}")


if __name__ == "__main__":
    main()
