"""Dump HID report descriptors + feature value caps for MCHOSE vendor collections.

Read-only: DeviceIoControl(HID_GET_REPORT_DESCRIPTOR) and HidP_GetValueCaps.
"""

import ctypes
import ctypes.wintypes as wt
import sys

sys.path.insert(0, r"D:\work\qd\poc")
import hid_probe as hp  # noqa: E402

hid = hp.hid
kernel32 = hp.kernel32

DeviceIoControl = kernel32.DeviceIoControl
DeviceIoControl.argtypes = [
    wt.HANDLE, wt.DWORD, ctypes.c_void_p, wt.DWORD,
    ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p,
]
DeviceIoControl.restype = wt.BOOL

IOCTL_HID_GET_REPORT_DESCRIPTOR = 0x000B0000


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [
        ("UsagePage", wt.USHORT),
        ("ReportID", ctypes.c_ubyte),
        ("IsAlias", wt.BOOLEAN),
        ("BitField", wt.USHORT),
        ("LinkCollection", wt.USHORT),
        ("LinkUsagePage", wt.USHORT),
        ("LinkUsage", wt.USHORT),
        ("IsRange", wt.BOOLEAN),
        ("IsStringRange", wt.BOOLEAN),
        ("IsDesignatorRange", wt.BOOLEAN),
        ("IsAbsolute", wt.BOOLEAN),
        ("HasNull", wt.BOOLEAN),
        ("Reserved", ctypes.c_ubyte),
        ("BitSize", wt.USHORT),
        ("ReportCount", wt.USHORT),
        ("Reserved2", wt.USHORT * 5),
        ("UnitsExp", wt.ULONG),
        ("Units", wt.ULONG),
        ("LogicalMin", wt.LONG),
        ("LogicalMax", wt.LONG),
        ("PhysicalMin", wt.LONG),
        ("PhysicalMax", wt.LONG),
        ("Union1", wt.ULONG),
        ("Union2", wt.ULONG),
        ("Union3", wt.ULONG),
        ("Union4", wt.ULONG),
        ("Union5", wt.ULONG),
        ("Union6", wt.ULONG),
    ]


HidP_GetValueCaps = hid.HidP_GetValueCaps
HidP_GetValueCaps.argtypes = [
    ctypes.c_int, ctypes.POINTER(HIDP_VALUE_CAPS), ctypes.POINTER(wt.USHORT), ctypes.c_void_p
]

HIDP_FEATURE = 2


def dump_descriptor(h):
    size = wt.DWORD(0)
    DeviceIoControl(h, IOCTL_HID_GET_REPORT_DESCRIPTOR, None, 0, None, 0, ctypes.byref(size), None)
    if not size.value:
        return b""
    buf = ctypes.create_string_buffer(size.value)
    if not DeviceIoControl(h, IOCTL_HID_GET_REPORT_DESCRIPTOR, None, 0, buf, size.value,
                           ctypes.byref(size), None):
        return b""
    return buf.raw[: size.value]


def parse_items(desc):
    """Very small HID item parser: enough to see report IDs and sizes."""
    i = 0
    out = []
    while i < len(desc):
        b = desc[i]
        if b == 0xFE:  # long item
            ln = desc[i + 1]
            out.append(("long", desc[i + 3:i + 3 + ln].hex()))
            i += 3 + ln
            continue
        size = {0: 0, 1: 1, 2: 2, 3: 4}[b & 0x03]
        tag = b & 0xFC
        val = int.from_bytes(desc[i + 1:i + 1 + size], "little") if size else 0
        out.append((tag, val, size))
        i += 1 + size
    return out


NAMES = {
    0x04: "UsagePage", 0x08: "Usage", 0x14: "LogicalMin", 0x24: "LogicalMax",
    0x74: "ReportSize", 0x84: "ReportID", 0x94: "ReportCount", 0xB4: "Feature",
    0xA4: "Collection", 0xC4: "EndCollection", 0x80: "Input", 0x90: "Output",
    0x64: "Unit", 0x54: "UnitExponent", 0x34: "PhysicalMin", 0x44: "PhysicalMax",
}


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
            if caps is None or caps.UsagePage not in (0xFF01, 0xFF0B):
                continue
            print(f"\n=== {attrs.VendorID:04X}:{attrs.ProductID:04X} "
                  f"upage={caps.UsagePage:#06x} usage={caps.Usage:#06x} "
                  f"in={caps.InputReportByteLength} out={caps.OutputReportByteLength} "
                  f"feat={caps.FeatureReportByteLength}")
            desc = dump_descriptor(h)
            print(f"  descriptor {len(desc)} bytes: {desc.hex()}")
            items = parse_items(desc)
            cur = []
            for tag, val, size in items:
                name = NAMES.get(tag, hex(tag))
                cur.append(f"{name}={val:#x}" if size else name)
                if tag in (0xB4, 0x80, 0x90, 0xC4):
                    print("   ", " ".join(cur))
                    cur = []

            # feature value caps: report id + bit size
            num = wt.USHORT(0)
            HidP_GetValueCaps(HIDP_FEATURE, None, ctypes.byref(num), None)
            if num.value:
                caps_arr = (HIDP_VALUE_CAPS * num.value)()
                n2 = wt.USHORT(num.value)
                if HidP_GetValueCaps(HIDP_FEATURE, caps_arr, ctypes.byref(n2), None) == 0x00110000:
                    for k in range(n2.value):
                        c = caps_arr[k]
                        print(f"    feat rid={c.ReportID:#04x} upage={c.UsagePage:#06x} "
                              f"usages={c.Union1:#x} bits={c.BitSize} count={c.ReportCount}")
        finally:
            hp.CloseHandle(h)


if __name__ == "__main__":
    main()
