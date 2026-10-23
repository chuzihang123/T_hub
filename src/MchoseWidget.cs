// MCHOSE Widget - floating battery/DPI monitor for MCHOSE mice.
// Built with the in-box .NET Framework 4.8 compiler (C# 5).
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

namespace MchoseWidget
{
    internal static class Hid
    {
        public const int DIGCF_PRESENT = 0x02;
        public const int DIGCF_DEVICEINTERFACE = 0x10;
        public const uint GENERIC_READ = 0x80000000;
        public const uint GENERIC_WRITE = 0x40000000;
        public const uint FILE_SHARE_READ = 1;
        public const uint FILE_SHARE_WRITE = 2;
        public const uint OPEN_EXISTING = 3;
        public static readonly IntPtr INVALID_HANDLE = new IntPtr(-1);

        [StructLayout(LayoutKind.Sequential)]
        public struct GUID
        {
            public uint Data1;
            public ushort Data2;
            public ushort Data3;
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 8)]
            public byte[] Data4;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct SP_DEVICE_INTERFACE_DATA
        {
            public int cbSize;
            public GUID InterfaceClassGuid;
            public int Flags;
            public IntPtr Reserved;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct HIDD_ATTRIBUTES
        {
            public int Size;
            public ushort VendorID;
            public ushort ProductID;
            public ushort VersionNumber;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct HIDP_CAPS
        {
            public ushort Usage;
            public ushort UsagePage;
            public ushort InputReportByteLength;
            public ushort OutputReportByteLength;
            public ushort FeatureReportByteLength;
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 17)]
            public ushort[] Reserved;
            public ushort NumberLinkCollectionNodes;
            public ushort NumberInputButtonCaps;
            public ushort NumberInputValueCaps;
            public ushort NumberInputDataIndices;
            public ushort NumberOutputButtonCaps;
            public ushort NumberOutputValueCaps;
            public ushort NumberOutputDataIndices;
            public ushort NumberFeatureButtonCaps;
            public ushort NumberFeatureValueCaps;
            public ushort NumberFeatureDataIndices;
        }

        [DllImport("hid.dll")]
        public static extern bool HidD_GetAttributes(IntPtr h, ref HIDD_ATTRIBUTES a);
        [DllImport("hid.dll")]
        public static extern bool HidD_GetPreparsedData(IntPtr h, out IntPtr data);
        [DllImport("hid.dll")]
        public static extern bool HidD_FreePreparsedData(IntPtr data);
        [DllImport("hid.dll")]
        public static extern int HidP_GetCaps(IntPtr data, ref HIDP_CAPS caps);
        [DllImport("hid.dll")]
        public static extern bool HidD_GetFeature(IntPtr h, byte[] buf, int len);
        [DllImport("hid.dll")]
        public static extern bool HidD_SetFeature(IntPtr h, byte[] buf, int len);
        [DllImport("hid.dll", CharSet = CharSet.Unicode)]
        public static extern bool HidD_GetProductString(IntPtr h, StringBuilder s, int len);

        [DllImport("setupapi.dll", CharSet = CharSet.Unicode)]
        public static extern IntPtr SetupDiGetClassDevs(ref GUID g, IntPtr enumerator, IntPtr hwnd, int flags);
        [DllImport("setupapi.dll")]
        public static extern bool SetupDiEnumDeviceInterfaces(IntPtr devs, IntPtr devInfo, ref GUID g, int index, ref SP_DEVICE_INTERFACE_DATA data);
        [DllImport("setupapi.dll", CharSet = CharSet.Unicode)]
        public static extern bool SetupDiGetDeviceInterfaceDetail(IntPtr devs, ref SP_DEVICE_INTERFACE_DATA data, IntPtr detail, int size, ref int required, IntPtr devInfo);
        [DllImport("setupapi.dll")]
        public static extern bool SetupDiDestroyDeviceInfoList(IntPtr devs);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        public static extern IntPtr CreateFile(string name, uint access, uint share, IntPtr sa, uint disposition, uint flags, IntPtr template);
        [DllImport("kernel32.dll", SetLastError = true)]
        public static extern bool CloseHandle(IntPtr h);

        public static GUID HidGuid()
        {
            GUID g = new GUID();
            g.Data1 = 0x4D1E55B2;
            g.Data2 = 0xF16F;
            g.Data3 = 0x11CF;
            g.Data4 = new byte[] { 0x88, 0xCB, 0x00, 0x11, 0x11, 0x00, 0x00, 0x30 };
            return g;
        }

        public static List<string> Enumerate()
        {
            List<string> paths = new List<string>();
            GUID g = HidGuid();
            IntPtr devs = SetupDiGetClassDevs(ref g, IntPtr.Zero, IntPtr.Zero, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
            if (devs == INVALID_HANDLE) return paths;
            try
            {
                int index = 0;
                while (true)
                {
                    SP_DEVICE_INTERFACE_DATA did = new SP_DEVICE_INTERFACE_DATA();
                    did.cbSize = Marshal.SizeOf(typeof(SP_DEVICE_INTERFACE_DATA));
                    if (!SetupDiEnumDeviceInterfaces(devs, IntPtr.Zero, ref g, index, ref did)) break;
                    index++;
                    int required = 0;
                    SetupDiGetDeviceInterfaceDetail(devs, ref did, IntPtr.Zero, 0, ref required, IntPtr.Zero);
                    IntPtr buf = Marshal.AllocHGlobal(required);
                    try
                    {
                        Marshal.WriteInt32(buf, IntPtr.Size == 8 ? 8 : 6);
                        if (SetupDiGetDeviceInterfaceDetail(devs, ref did, buf, required, ref required, IntPtr.Zero))
                        {
                            paths.Add(Marshal.PtrToStringUni(new IntPtr(buf.ToInt64() + 4)));
                        }
                    }
                    finally { Marshal.FreeHGlobal(buf); }
                }
            }
            finally { SetupDiDestroyDeviceInfoList(devs); }
            return paths;
        }
    }

    internal sealed class MouseDevice
    {
        public string Path;
        public string Name = "MCHOSE";
        public ushort VendorId;
        public ushort ProductId;

        public bool Awake;
        public int Battery = -1;
        public int Charge;
        public int ConnectMode;
        public int ActiveStage;
        public int[] Stages = new int[6];
        public int StageCount = 6;
        public bool IsVgn;
        public string Error = "";

        public string Key { get { return string.Format("{0:X4}:{1:X4}", VendorId, ProductId); } }
    }

    internal static class Protocol
    {
        public static MouseDevice TryOpen(string path)
        {
            IntPtr h = Hid.CreateFile(path, Hid.GENERIC_READ | Hid.GENERIC_WRITE,
                Hid.FILE_SHARE_READ | Hid.FILE_SHARE_WRITE, IntPtr.Zero, Hid.OPEN_EXISTING, 0, IntPtr.Zero);
            if (h == Hid.INVALID_HANDLE) return null;
            try
            {
                Hid.HIDD_ATTRIBUTES attrs = new Hid.HIDD_ATTRIBUTES();
                attrs.Size = Marshal.SizeOf(typeof(Hid.HIDD_ATTRIBUTES));
                if (!Hid.HidD_GetAttributes(h, ref attrs)) return null;
                if (attrs.VendorID != 0x5253 && attrs.VendorID != 0x3837) return null;

                IntPtr preparsed;
                if (!Hid.HidD_GetPreparsedData(h, out preparsed)) return null;
                Hid.HIDP_CAPS caps = new Hid.HIDP_CAPS();
                try
                {
                    if (Hid.HidP_GetCaps(preparsed, ref caps) != 0x00110000) return null;
                }
                finally { Hid.HidD_FreePreparsedData(preparsed); }
                if (caps.UsagePage != 0xFF01) return null;

                MouseDevice dev = new MouseDevice();
                dev.Path = path;
                dev.VendorId = attrs.VendorID;
                dev.ProductId = attrs.ProductID;
                StringBuilder sb = new StringBuilder(256);
                if (Hid.HidD_GetProductString(h, sb, sb.Capacity * 2)) dev.Name = sb.ToString();
                if (string.IsNullOrEmpty(dev.Name)) dev.Name = "MCHOSE " + dev.Key;
                return dev;
            }
            finally { Hid.CloseHandle(h); }
        }

        // Sends one feature-report command and returns the response payload
        // (report id stripped, command echo verified, bytes un-inverted).
        public static byte[] Transact(IntPtr h, byte reportId, int payloadLen, byte cmd, int waitMs)
        {
            byte[] req = new byte[1 + payloadLen];
            req[0] = reportId;
            for (int i = 0; i < payloadLen; i++) req[1 + i] = 0xFF;
            req[1] = (byte)(cmd ^ 0xFF);
            if (!Hid.HidD_SetFeature(h, req, req.Length)) return null;
            Thread.Sleep(waitMs);

            byte[] resp = new byte[1 + payloadLen];
            resp[0] = reportId;
            if (!Hid.HidD_GetFeature(h, resp, resp.Length)) return null;
            if (resp[0] != reportId) return null;
            if ((byte)(resp[1] ^ 0xFF) != cmd) return null;

            // The echoed command rides in payload byte 0, so the data payload
            // is one byte shorter than the frame.
            byte[] data = new byte[payloadLen - 1];
            for (int i = 0; i < data.Length; i++) data[i] = (byte)(resp[2 + i] ^ 0xFF);
            return data;
        }

        public static MouseDevice TryOpenHeadset(string path)
        {
            IntPtr h = Hid.CreateFile(path, Hid.GENERIC_READ | Hid.GENERIC_WRITE,
                Hid.FILE_SHARE_READ | Hid.FILE_SHARE_WRITE, IntPtr.Zero, Hid.OPEN_EXISTING, 0, IntPtr.Zero);
            if (h == Hid.INVALID_HANDLE) return null;
            try
            {
                Hid.HIDD_ATTRIBUTES attrs = new Hid.HIDD_ATTRIBUTES();
                attrs.Size = Marshal.SizeOf(typeof(Hid.HIDD_ATTRIBUTES));
                if (!Hid.HidD_GetAttributes(h, ref attrs)) return null;
                if (attrs.VendorID != 0x291D || attrs.ProductID != 0x385D) return null;

                IntPtr preparsed;
                if (!Hid.HidD_GetPreparsedData(h, out preparsed)) return null;
                Hid.HIDP_CAPS caps = new Hid.HIDP_CAPS();
                try
                {
                    if (Hid.HidP_GetCaps(preparsed, ref caps) != 0x00110000) return null;
                }
                finally { Hid.HidD_FreePreparsedData(preparsed); }
                if (caps.UsagePage != 0xFF90) return null;

                MouseDevice dev = new MouseDevice();
                dev.Path = path;
                dev.VendorId = attrs.VendorID;
                dev.ProductId = attrs.ProductID;
                dev.Name = "MCHOSE V9 PRO";
                return dev;
            }
            finally { Hid.CloseHandle(h); }
        }

        public static MouseDevice TryOpenKeyboard(string path)
        {
            IntPtr h = Hid.CreateFile(path, Hid.GENERIC_READ | Hid.GENERIC_WRITE,
                Hid.FILE_SHARE_READ | Hid.FILE_SHARE_WRITE, IntPtr.Zero, Hid.OPEN_EXISTING, 0, IntPtr.Zero);
            if (h == Hid.INVALID_HANDLE) return null;
            try
            {
                Hid.HIDD_ATTRIBUTES attrs = new Hid.HIDD_ATTRIBUTES();
                attrs.Size = Marshal.SizeOf(typeof(Hid.HIDD_ATTRIBUTES));
                if (!Hid.HidD_GetAttributes(h, ref attrs)) return null;
                if (attrs.VendorID != 0x1A2C || attrs.ProductID != 0x8FFF) return null;
                IntPtr preparsed;
                if (!Hid.HidD_GetPreparsedData(h, out preparsed)) return null;
                Hid.HIDP_CAPS caps = new Hid.HIDP_CAPS();
                try
                {
                    if (Hid.HidP_GetCaps(preparsed, ref caps) != 0x00110000) return null;
                }
                finally { Hid.HidD_FreePreparsedData(preparsed); }
                if (caps.UsagePage != 0xFF02) return null;
                MouseDevice dev = new MouseDevice();
                dev.Path = path;
                dev.VendorId = attrs.VendorID;
                dev.ProductId = attrs.ProductID;
                dev.Name = "LANGTU T75";
                return dev;
            }
            finally { Hid.CloseHandle(h); }
        }

        public static void RefreshKeyboard(MouseDevice dev)
        {
            IntPtr h = Hid.CreateFile(dev.Path, Hid.GENERIC_READ | Hid.GENERIC_WRITE,
                Hid.FILE_SHARE_READ | Hid.FILE_SHARE_WRITE, IntPtr.Zero, Hid.OPEN_EXISTING, 0x40000000, IntPtr.Zero);
            if (h == Hid.INVALID_HANDLE) { dev.Awake = false; dev.Error = "无法打开"; return; }
            try
            {
                byte[] readBuf = new byte[65];
                Native.OVERLAPPED rov = new Native.OVERLAPPED();
                IntPtr rev = Native.CreateEvent(IntPtr.Zero, true, false, null);
                rov.hEvent = rev;
                uint got = 0;
                Native.ReadFile(h, readBuf, 65, out got, ref rov);

                byte[] outBuf = new byte[65];
                outBuf[0] = 0x00;
                outBuf[1] = 0xAA;
                outBuf[2] = 0x55;
                outBuf[3] = 0xCC;
                outBuf[4] = 0x33;
                outBuf[5] = 0x0E;
                Native.OVERLAPPED wov = new Native.OVERLAPPED();
                IntPtr wev = Native.CreateEvent(IntPtr.Zero, true, false, null);
                wov.hEvent = wev;
                uint wrote = 0;
                Native.WriteFile(h, outBuf, 65, out wrote, ref wov);
                Native.WaitForSingleObject(wev, 400);

                if (Native.WaitForSingleObject(rev, 700) == 0)
                {
                    Native.GetOverlappedResult(h, ref rov, out got, false);
                    if (got >= 7 && readBuf[1] == 0xAA && readBuf[2] == 0x55
                        && readBuf[3] == 0xCC && readBuf[4] == 0x33 && readBuf[5] == 0x0E)
                    {
                        int level = readBuf[6];
                        dev.Battery = level;
                        dev.Charge = 0;
                        dev.Awake = level > 0 && level <= 100;
                        dev.Error = dev.Awake ? "" : "休眠";
                        return;
                    }
                }
                dev.Awake = false;
                dev.Error = "无信号";
            }
            catch { dev.Awake = false; dev.Error = "读取失败"; }
            finally { Hid.CloseHandle(h); }
        }

        // --- VGN keyboard ---------------------------------------------------
        // VGN's VHUB drives its keyboards through a vendor collection
        // (usage page 0xFFA0 / 0xFFB0, usage 1) with the sparklinkplayjoy
        // protocol, which the installer ships as readable TypeScript under
        // vendor/vgn/asar/node_modules/@sparklinkplayjoy. Frames are a fixed
        // 64 bytes and the three-mode info command 0x0D 0x01 answers
        //   [0x0D][status][mode][charge][battery]
        // A collection is only claimed after that command actually answers,
        // so an unrelated vendor page is never mistaken for a keyboard.

        private static byte[] VgnInfoPacket()
        {
            byte[] p = new byte[64];
            p[0] = 0x0D;
            p[1] = 0x01;
            return p;
        }

        private static bool VgnExchange(string path, byte[] payload, int waitMs, out byte[] reply)
        {
            reply = null;
            IntPtr h = Hid.CreateFile(path, Hid.GENERIC_READ | Hid.GENERIC_WRITE,
                Hid.FILE_SHARE_READ | Hid.FILE_SHARE_WRITE, IntPtr.Zero, Hid.OPEN_EXISTING,
                0x40000000, IntPtr.Zero);
            if (h == Hid.INVALID_HANDLE) return false;

            IntPtr rev = IntPtr.Zero;
            IntPtr wev = IntPtr.Zero;
            try
            {
                byte[] inBuf = new byte[65];
                Native.OVERLAPPED rov = new Native.OVERLAPPED();
                rev = Native.CreateEvent(IntPtr.Zero, true, false, null);
                rov.hEvent = rev;
                uint got = 0;
                Native.ReadFile(h, inBuf, inBuf.Length, out got, ref rov);

                byte[] outBuf = new byte[1 + payload.Length];
                outBuf[0] = 0x00;
                Array.Copy(payload, 0, outBuf, 1, payload.Length);
                Native.OVERLAPPED wov = new Native.OVERLAPPED();
                wev = Native.CreateEvent(IntPtr.Zero, true, false, null);
                wov.hEvent = wev;
                uint wrote = 0;
                Native.WriteFile(h, outBuf, outBuf.Length, out wrote, ref wov);
                Native.WaitForSingleObject(wev, (uint)waitMs);

                if (Native.WaitForSingleObject(rev, (uint)waitMs) != 0) return false;
                Native.GetOverlappedResult(h, ref rov, out got, false);
                if (got < 5) return false;
                reply = new byte[(int)got];
                Array.Copy(inBuf, reply, (int)got);
                return true;
            }
            catch { return false; }
            finally
            {
                if (rev != IntPtr.Zero) Hid.CloseHandle(rev);
                if (wev != IntPtr.Zero) Hid.CloseHandle(wev);
                Hid.CloseHandle(h);
            }
        }

        private static bool VgnParse(MouseDevice dev, byte[] reply)
        {
            // The HID stack may or may not keep the report id in the buffer,
            // so accept the vendor frame at either offset.
            int o = (reply.Length > 5 && reply[1] == 0x0D) ? 1 : 0;
            if (reply.Length < o + 5 || reply[o] != 0x0D) return false;
            int status = reply[o + 1];
            int mode = reply[o + 2];
            int charge = reply[o + 3];
            int battery = reply[o + 4];
            if (status != 0) { dev.Error = "状态" + status; return false; }
            if (battery <= 0 || battery > 100) { dev.Error = "电量" + battery; return false; }
            dev.Battery = battery;
            dev.Charge = charge;
            dev.ConnectMode = mode;
            dev.Error = "";
            return true;
        }

        public static MouseDevice TryOpenVgn(string path)
        {
            MouseDevice dev = null;
            IntPtr h = Hid.CreateFile(path, Hid.GENERIC_READ | Hid.GENERIC_WRITE,
                Hid.FILE_SHARE_READ | Hid.FILE_SHARE_WRITE, IntPtr.Zero, Hid.OPEN_EXISTING, 0, IntPtr.Zero);
            if (h == Hid.INVALID_HANDLE) return null;
            try
            {
                Hid.HIDD_ATTRIBUTES attrs = new Hid.HIDD_ATTRIBUTES();
                attrs.Size = Marshal.SizeOf(typeof(Hid.HIDD_ATTRIBUTES));
                if (!Hid.HidD_GetAttributes(h, ref attrs)) return null;

                IntPtr preparsed;
                if (!Hid.HidD_GetPreparsedData(h, out preparsed)) return null;
                Hid.HIDP_CAPS caps = new Hid.HIDP_CAPS();
                try
                {
                    if (Hid.HidP_GetCaps(preparsed, ref caps) != 0x00110000) return null;
                }
                finally { Hid.HidD_FreePreparsedData(preparsed); }

                if (caps.Usage != 1) return null;
                if (caps.UsagePage != 0xFFA0 && caps.UsagePage != 0xFFB0 && caps.UsagePage != 0xFF60)
                    return null;

                dev = new MouseDevice();
                dev.Path = path;
                dev.VendorId = attrs.VendorID;
                dev.ProductId = attrs.ProductID;
                dev.IsVgn = true;
                StringBuilder sb = new StringBuilder(256);
                if (Hid.HidD_GetProductString(h, sb, sb.Capacity * 2) && sb.Length > 0)
                    dev.Name = sb.ToString();
                else
                    dev.Name = "VGN " + string.Format("{0:X4}:{1:X4}", attrs.VendorID, attrs.ProductID);
            }
            finally { Hid.CloseHandle(h); }

            if (dev == null) return null;
            byte[] reply;
            if (!VgnExchange(path, VgnInfoPacket(), 500, out reply)) return null;
            if (!VgnParse(dev, reply)) return null;
            dev.Awake = true;
            return dev;
        }

        public static void RefreshVgn(MouseDevice dev)
        {
            byte[] reply;
            if (!VgnExchange(dev.Path, VgnInfoPacket(), 500, out reply))
            {
                dev.Awake = false;
                dev.Error = "无响应";
                return;
            }
            dev.Awake = VgnParse(dev, reply);
        }

        public static void RefreshHeadset(MouseDevice dev)
        {
            IntPtr h = Hid.CreateFile(dev.Path, Hid.GENERIC_READ | Hid.GENERIC_WRITE,
                Hid.FILE_SHARE_READ | Hid.FILE_SHARE_WRITE, IntPtr.Zero, Hid.OPEN_EXISTING, 0x40000000, IntPtr.Zero);
            if (h == Hid.INVALID_HANDLE)
            {
                dev.Awake = false;
                dev.Error = "无法打开";
                return;
            }
            try
            {
                byte[] readBuf = new byte[64];
                Native.OVERLAPPED rov = new Native.OVERLAPPED();
                IntPtr rev = Native.CreateEvent(IntPtr.Zero, true, false, null);
                rov.hEvent = rev;
                uint got = 0;
                Native.ReadFile(h, readBuf, 64, out got, ref rov);

                byte[] outBuf = new byte[64];
                outBuf[0] = 0x55;
                outBuf[1] = 0x65;
                outBuf[2] = 0x01;
                Native.OVERLAPPED wov = new Native.OVERLAPPED();
                IntPtr wev = Native.CreateEvent(IntPtr.Zero, true, false, null);
                wov.hEvent = wev;
                uint wrote = 0;
                Native.WriteFile(h, outBuf, 64, out wrote, ref wov);
                Native.WaitForSingleObject(wev, 400);

                if (Native.WaitForSingleObject(rev, 600) == 0)
                {
                    Native.GetOverlappedResult(h, ref rov, out got, false);
                    if (got >= 4 && readBuf[0] == 0x55 && readBuf[1] == 0x65)
                    {
                        dev.Battery = readBuf[2];
                        dev.Charge = readBuf[3] == 3 ? 1 : 0;
                        dev.Awake = dev.Battery > 0 && dev.Battery <= 100;
                        dev.Error = dev.Awake ? "" : "休眠";
                    }
                }
                else
                {
                    dev.Awake = false;
                    dev.Error = "无信号";
                }
            }
            catch
            {
                dev.Awake = false;
                dev.Error = "读取失败";
            }
            finally { Hid.CloseHandle(h); }
        }

        public static bool Refresh(MouseDevice dev)
        {
            IntPtr h = Hid.CreateFile(dev.Path, Hid.GENERIC_READ | Hid.GENERIC_WRITE,
                Hid.FILE_SHARE_READ | Hid.FILE_SHARE_WRITE, IntPtr.Zero, Hid.OPEN_EXISTING, 0, IntPtr.Zero);
            if (h == Hid.INVALID_HANDLE)
            {
                dev.Error = "无法打开设备";
                dev.Awake = false;
                return false;
            }
            try
            {
                byte[] info = Transact(h, 0x11, 20, 0x03, 40);
                if (info == null) { dev.Error = "无应答"; dev.Awake = false; return false; }
                dev.ConnectMode = info[7];

                // The mouse answers from a low-power state with zeroed frames;
                // retry until it produces a plausible battery or gives up.
                int battery = -1;
                int charge = 0;
                int linkMode = dev.ConnectMode;
                for (int attempt = 0; attempt < 4 && battery < 0; attempt++)
                {
                    byte[] bat = Transact(h, 0x11, 20, 0x06, 60);
                    if (bat != null)
                    {
                        ushort vid = (ushort)(bat[0] | (bat[1] << 8));
                        ushort pid = (ushort)(bat[2] | (bat[3] << 8));
                        int level = bat[9];
                        if ((vid != 0 || pid != 0) && level > 0 && level <= 100)
                        {
                            battery = level;
                            charge = bat[10];
                            linkMode = (bat[8] >> 3) & 1;
                        }
                    }
                    if (battery < 0) Thread.Sleep(40);
                }
                if (battery < 0) Thread.Sleep(60);

                dev.Awake = battery >= 0;
                if (battery >= 0)
                {
                    dev.Battery = battery;
                    dev.Charge = charge;
                    dev.ConnectMode = linkMode;
                    dev.Error = "";
                }
                else if (dev.Battery >= 0) dev.Error = "休眠";
                else dev.Error = "未唤醒";

                byte[] cfg = null;
                for (int attempt = 0; attempt < 3; attempt++)
                {
                    cfg = Transact(h, 0x12, 64, 0x67, 220);
                    if (cfg != null && (cfg[4] != 0 || cfg[5] != 0)) break;
                    Thread.Sleep(60);
                }
                if (cfg != null && (cfg[4] != 0 || cfg[5] != 0))
                {
                    dev.ActiveStage = cfg[1] & 0x0F;
                    dev.StageCount = cfg[16];
                    if (dev.StageCount < 1 || dev.StageCount > 6) dev.StageCount = 6;
                    for (int i = 0; i < 6; i++)
                        dev.Stages[i] = cfg[4 + i * 2] | (cfg[5 + i * 2] << 8);
                }
                return true;
            }
            catch (Exception e)
            {
                dev.Error = e.Message;
                dev.Awake = false;
                return false;
            }
            finally { Hid.CloseHandle(h); }
        }
    }

    internal sealed class Widget : Form
    {
        private readonly List<MouseDevice> _devices = new List<MouseDevice>();
        private readonly object _lock = new object();
        private readonly NotifyIcon _tray;
        private readonly System.Windows.Forms.Timer _uiTimer;
        private readonly System.Windows.Forms.Timer _pollTimer;
        private readonly string _statePath;
        private ContextMenuStrip _menu;
        private ToolStripMenuItem _miTop, _miLock, _miStartup;
        private bool _polling;
        private static bool _saveFrame = false;
        private bool _drag;
        private bool _locked;
        private bool _pinned;
        private int _opacity = 170;
        private Bitmap _backdrop;
        private bool _backdropDirty = true;
        private int _ticks;
        private string _lastSig = "";
        private int _lastX = int.MinValue, _lastY = int.MinValue;
        private static readonly Dictionary<string, MouseDevice> LastKnown = new Dictionary<string, MouseDevice>();
        private readonly Dictionary<string, DateTime> _lastSeen = new Dictionary<string, DateTime>();
        private ToolStripMenuItem[] _opacityItems;
        private static readonly int[] OpacityLevels = new int[] { 55, 68, 82 };
        private Point _dragStart;
        private Font _fName, _fPct, _fSmall, _fTiny, _fTitle, _fSub;

        private const int WS_EX_LAYERED = 0x00080000;
        private const int WS_EX_TOOLWINDOW = 0x00000080;

        public Widget()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer, true);
            AutoScaleMode = AutoScaleMode.None;
            AutoScaleDimensions = new SizeF(96F, 96F);
            FormBorderStyle = FormBorderStyle.None;
            StartPosition = FormStartPosition.Manual;
            TopMost = false;
            ShowInTaskbar = false;
            BackColor = Color.Black;
            ClientSize = new Size(224, 132);

            _statePath = System.IO.Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "MCHOSE Widget", "state.txt");
            Location = LoadPosition();
            _pinned = _locked && TopMost;

            _fName = PickFont(13.5f, FontStyle.Bold);
            _fPct = PickFont(16f, FontStyle.Bold);
            _fTitle = PickFont(11.5f, FontStyle.Bold);
            _fSub = PickFont(9f, FontStyle.Regular);
            _fSmall = PickFont(9f, FontStyle.Regular);
            _fTiny = PickFont(8.5f, FontStyle.Regular);

            BuildMenu();

            _tray = new NotifyIcon();
            _tray.Icon = MakeIcon(0);
            _tray.Text = "MCHOSE 电量";
            _tray.Visible = true;
            _tray.ContextMenuStrip = _menu;
            _tray.DoubleClick += delegate { Visible = !Visible; if (Visible) { Invalidate(); } };

            _uiTimer = new System.Windows.Forms.Timer();
            _uiTimer.Interval = 1000;
            _uiTimer.Tick += delegate
            {
                string sig = Signature();
                if (sig != _lastSig)
                {
                    _lastSig = sig;
                    Render();
                }
            };
            _uiTimer.Start();

            _pollTimer = new System.Windows.Forms.Timer();
            _pollTimer.Interval = 5000;
            _pollTimer.Tick += delegate { Poll(); };
            _pollTimer.Start();

            Shown += delegate
            {
                System.IO.File.AppendAllText(@"D:\work\qd\build\pos.log",
                    string.Format("shown left={0} top={1} wa={2}\r\n", Left, Top, Screen.PrimaryScreen.WorkingArea));
                Invalidate();
                Poll();
            };
        }

        protected override CreateParams CreateParams
        {
            get
            {
                CreateParams cp = base.CreateParams;
                cp.ExStyle |= WS_EX_LAYERED | WS_EX_TOOLWINDOW;
                return cp;
            }
        }

        private void BuildMenu()
        {
            _menu = new ContextMenuStrip();
            _miTop = new ToolStripMenuItem("置顶显示");
            _miTop.CheckOnClick = true;
            _miTop.Checked = false;
            _miTop.CheckedChanged += delegate
            {
                TopMost = _miTop.Checked;
                Invalidate();
                SaveState();
            };
            _miLock = new ToolStripMenuItem("锁定位置");
            _miLock.CheckOnClick = true;
            _miLock.CheckedChanged += delegate
            {
                _locked = _miLock.Checked;
                Invalidate();
                SaveState();
            };
            _menu.Items.Add(_miTop);
            _menu.Items.Add(_miLock);

            ToolStripMenuItem opMenu = new ToolStripMenuItem("透明度");
            _opacityItems = new ToolStripMenuItem[OpacityLevels.Length];
            for (int i = 0; i < OpacityLevels.Length; i++)
            {
                int level = OpacityLevels[i];
                ToolStripMenuItem item = new ToolStripMenuItem(level + "%");
                item.Click += delegate { SetOpacity(level); };
                opMenu.DropDownItems.Add(item);
                _opacityItems[i] = item;
            }
            _menu.Items.Add(opMenu);
            UpdateOpacityChecks();
            _miStartup = new ToolStripMenuItem("开机自动启动");
            _miStartup.CheckOnClick = true;
            _miStartup.Checked = Startup.IsEnabled();
            _miStartup.CheckedChanged += delegate { Startup.Set(_miStartup.Checked); };
            _menu.Items.Add(_miStartup);
            _menu.Items.Add(new ToolStripSeparator());
            _menu.Items.Add("刷新", null, delegate { Poll(); });
            _menu.Items.Add("退出", null, delegate { Close(); });
            ContextMenuStrip = _menu;
        }

        private void SetOpacity(int percent)
        {
            _opacity = Math.Max(30, Math.Min(255, percent * 255 / 100));
            UpdateOpacityChecks();
            Invalidate();
            SaveState();
        }

        private void UpdateOpacityChecks()
        {
            if (_opacityItems == null) return;
            for (int i = 0; i < _opacityItems.Length; i++)
                _opacityItems[i].Checked = Math.Abs(_opacity - OpacityLevels[i] * 255 / 100) < 6;
        }

        private const string RunKey = @"Software\Microsoft\Windows\CurrentVersion\Run";
        private const string RunName = "MCHOSE Widget";

        private Point LoadPosition()
        {
            try
            {
                if (System.IO.File.Exists(_statePath))
                {
                    string[] parts = System.IO.File.ReadAllText(_statePath).Split(',');
                    if (parts.Length >= 2)
                    {
                        int x, y;
                        if (int.TryParse(parts[0], out x) && int.TryParse(parts[1], out y))
                        {
                            Rectangle vs = SystemInformation.VirtualScreen;
                            if (x > vs.Left - Width + 40 && x < vs.Right - 40
                                && y > vs.Top - 10 && y < vs.Bottom - 40)
                            {
                                if (parts.Length >= 5)
                                {
                                    int op;
                                    if (int.TryParse(parts[4], out op) && op >= 30 && op <= 255) _opacity = op;
                                }
                                if (parts.Length >= 4)
                                {
                                    bool locked, top;
                                    bool.TryParse(parts[2], out locked);
                                    bool.TryParse(parts[3], out top);
                                    _locked = locked;
                                    TopMost = top;
                                }
                                return new Point(x, y);
                            }
                        }
                    }
                }
            }
            catch { }
            Screen s = Screen.PrimaryScreen;
            return new Point(s.WorkingArea.Right - Width - 24, s.WorkingArea.Bottom - Height - 24);
        }

        private void SaveState()
        {
            try
            {
                string dir = System.IO.Path.GetDirectoryName(_statePath);
                if (!System.IO.Directory.Exists(dir)) System.IO.Directory.CreateDirectory(dir);
                System.IO.File.WriteAllText(_statePath, string.Format("{0},{1},{2},{3},{4}",
                    Left, Top, _locked, TopMost, _opacity));
            }
            catch { }
        }

        private void Poll()
        {
            if (_polling) return;
            _polling = true;
            ThreadPool.QueueUserWorkItem(delegate
            {
                try
                {
                    List<string> paths = Hid.Enumerate();
                    List<MouseDevice> found = new List<MouseDevice>();
                    foreach (string p in paths)
                    {
                        MouseDevice d = Protocol.TryOpen(p);
                        if (d == null) d = Protocol.TryOpenHeadset(p);
                        if (d == null) d = Protocol.TryOpenKeyboard(p);
                        if (d == null) d = Protocol.TryOpenVgn(p);
                        if (d != null) found.Add(d);
                    }
                    foreach (MouseDevice d in found)
                    {
                        if (d.IsVgn) Protocol.RefreshVgn(d);
                        else if (d.ProductId == 0x385D) Protocol.RefreshHeadset(d);
                        else if (d.ProductId == 0x8FFF && d.VendorId == 0x1A2C) Protocol.RefreshKeyboard(d);
                        else Protocol.Refresh(d);
                        MouseDevice prev;
                        if (LastKnown.TryGetValue(d.Key, out prev))
                        {
                            if (!d.Awake && prev.Battery >= 0)
                            {
                                d.Battery = prev.Battery;
                                d.Charge = prev.Charge;
                                d.ActiveStage = prev.ActiveStage;
                                d.StageCount = prev.StageCount;
                                Array.Copy(prev.Stages, d.Stages, 6);
                                d.Error = "休眠";
                            }
                        }
                        if (d.Awake) LastKnown[d.Key] = d;
                    }
                    try
                    {
                        StringBuilder log = new StringBuilder();
                        foreach (MouseDevice d in found)
                        {
                            log.AppendFormat("{0} awake={1} bat={2} key={3} stage={4} count={5} dpi0={6} err={7}\r\n",
                                d.Name, d.Awake, d.Battery, d.Key, d.ActiveStage, d.StageCount,
                                d.Stages[0], d.Error);
                        }
                        System.IO.File.WriteAllText(@"D:\work\qd\build\state.log", log.ToString());
                    }
                    catch { }
                    DateTime now = DateTime.UtcNow;
                    List<MouseDevice> shown = new List<MouseDevice>();
                    foreach (MouseDevice d in found)
                    {
                        if (d.Awake) _lastSeen[d.Key] = now;
                        DateTime ts;
                        bool recent = _lastSeen.TryGetValue(d.Key, out ts)
                                      && (now - ts).TotalSeconds <= 6;
                        if (d.Awake || recent) shown.Add(d);
                    }
                    lock (_lock)
                    {
                        _devices.Clear();
                        _devices.AddRange(shown);
                    }
                    if (IsHandleCreated) BeginInvoke(new Action(delegate
                    {
                        int best = 0;
                        foreach (MouseDevice d in shown) if (d.Battery > best) best = d.Battery;
                        _tray.Icon = MakeIcon(best);
                        _tray.Text = "MCHOSE 电量 " + (best > 0 ? best + "%" : "--");
                        ApplyLayout(shown.Count);
                    }));
                }
                catch { }
                finally { _polling = false; }
            });
        }

        private static Icon MakeIcon(int pct)
        {
            Bitmap bmp = new Bitmap(32, 32);
            using (Graphics g = Graphics.FromImage(bmp))
            {
                g.SmoothingMode = SmoothingMode.AntiAlias;
                g.Clear(Color.Transparent);
                Color c = pct >= 60 ? Color.FromArgb(52, 199, 89) : pct >= 25 ? Color.FromArgb(255, 204, 0) : Color.FromArgb(255, 59, 48);
                using (Pen p = new Pen(Color.FromArgb(230, 235, 245), 2f))
                using (Brush b = new SolidBrush(c))
                {
                    g.DrawRectangle(p, 3, 10, 22, 12);
                    g.FillRectangle(b, 6, 13, 16 * Math.Max(pct, 3) / 100f, 6);
                    g.FillRectangle(p.Brush, 25, 14, 3, 4);
                }
            }
            return Icon.FromHandle(bmp.GetHicon());
        }

        private static Font PickFont(float size, FontStyle style)
        {
            string[] names = { "SF Pro Display", "SF Pro Text", "Segoe UI Variable Display", "Segoe UI" };
            foreach (string n in names)
            {
                try
                {
                    Font f = new Font(n, size, style);
                    if (string.Equals(f.Name, n, StringComparison.OrdinalIgnoreCase)) return f;
                    f.Dispose();
                }
                catch { }
            }
            return new Font("Segoe UI", size, style);
        }

        private static GraphicsPath RoundPath(Rectangle r, int radius)
        {
            GraphicsPath path = new GraphicsPath();
            int d = radius * 2;
            if (d > r.Height) d = Math.Max(2, r.Height);
            if (d > r.Width) d = Math.Max(2, r.Width);
            path.AddArc(r.X, r.Y, d, d, 180, 90);
            path.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            path.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            path.CloseFigure();
            return path;
        }

        private void DrawBattery(Graphics g, Rectangle r, int pct, bool charging, bool awake)
        {
            int bodyW = r.Width - 5;
            Rectangle body = new Rectangle(r.X, r.Y, bodyW, r.Height);
            using (GraphicsPath p = RoundPath(body, 5))
            using (Pen pen = new Pen(Color.FromArgb(awake ? 140 : 60, 235, 235, 240), 1.4f))
                g.DrawPath(pen, p);
            using (SolidBrush nub = new SolidBrush(Color.FromArgb(awake ? 140 : 60, 235, 235, 240)))
                g.FillRectangle(nub, r.Right - 4, r.Y + r.Height / 2 - 4, 3, 8);

            if (pct <= 0) return;
            Color fill = charging ? Color.FromArgb(52, 199, 89)
                       : pct <= 20 ? Color.FromArgb(255, 59, 48)
                       : pct <= 40 ? Color.FromArgb(255, 204, 0)
                       : Color.FromArgb(52, 199, 89);
            int w = (body.Width - 6) * pct / 100;
            if (w < 4) w = 4;
            Rectangle inner = new Rectangle(body.X + 3, body.Y + 3, w, body.Height - 6);
            using (GraphicsPath ip = RoundPath(inner, 3))
            using (SolidBrush b = new SolidBrush(fill))
                g.FillPath(b, ip);
        }

        private Rectangle PinRect()
        {
            return new Rectangle(Width - 30, 2, 26, 26);
        }

        private void DrawPin(Graphics g)
        {
            Rectangle r = PinRect();
            int cx = r.X + r.Width / 2;
            int top = r.Y + 7;
            Color c = _pinned ? Color.FromArgb(235, 26, 26, 30) : Color.FromArgb(105, 110, 110, 118);

            using (SolidBrush b = new SolidBrush(c))
                g.FillEllipse(b, cx - 4, top, 8, 8);
            using (Pen p = new Pen(c, 1.5f))
            {
                g.DrawLine(p, cx, top + 8, cx, top + 14);
                g.DrawLine(p, cx - 4, top + 14, cx + 4, top + 14);
            }
            if (_pinned)
            {
                using (SolidBrush dot = new SolidBrush(Color.FromArgb(235, 52, 199, 89)))
                    g.FillEllipse(dot, cx + 5, top - 1, 4, 4);
            }
        }

        private void TogglePin()
        {
            _pinned = !_pinned;
            _locked = _pinned;
            TopMost = _pinned;
            if (_miLock != null) _miLock.Checked = _locked;
            if (_miTop != null) _miTop.Checked = TopMost;
            SaveState();
            Render();
        }

        private void CaptureBackdrop()
        {
            try
            {
                Native.ShowWindow(Handle, 0);
                Thread.Sleep(12);
                Bitmap raw = new Bitmap(Width, Height, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
                try
                {
                    using (Graphics g = Graphics.FromImage(raw))
                        g.CopyFromScreen(Left, Top, 0, 0, new Size(Width, Height));
                }
                finally
                {
                    Native.ShowWindow(Handle, 4);
                }
                _backdrop = Gaussian(raw, 3, 20);
                raw.Dispose();
            }
            catch { _backdrop = null; }
            finally { _backdropDirty = false; }
        }

        private static Bitmap Gaussian(Bitmap src, int passes, int radius)
        {
            Bitmap dst = src;
            for (int i = 0; i < passes; i++)
                dst = BoxBlur(dst, radius);
            return dst;
        }

        private static Bitmap BoxBlur(Bitmap src, int radius)
        {
            int w = src.Width, h = src.Height;
            Bitmap dst = new Bitmap(w, h, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
            System.Drawing.Imaging.BitmapData sd = src.LockBits(new Rectangle(0, 0, w, h),
                System.Drawing.Imaging.ImageLockMode.ReadOnly, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
            System.Drawing.Imaging.BitmapData dd = dst.LockBits(new Rectangle(0, 0, w, h),
                System.Drawing.Imaging.ImageLockMode.WriteOnly, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
            try
            {
                int stride = sd.Stride;
                byte[] inBuf = new byte[stride * h];
                byte[] outBuf = new byte[stride * h];
                Marshal.Copy(sd.Scan0, inBuf, 0, inBuf.Length);
                for (int y = 0; y < h; y++)
                {
                    for (int x = 0; x < w; x++)
                    {
                        int r = 0, gg = 0, b = 0, n = 0;
                        for (int dy = -radius; dy <= radius; dy += 2)
                        {
                            int yy = y + dy;
                            if (yy < 0 || yy >= h) continue;
                            for (int dx = -radius; dx <= radius; dx += 2)
                            {
                                int xx = x + dx;
                                if (xx < 0 || xx >= w) continue;
                                int o = yy * stride + xx * 4;
                                b += inBuf[o]; gg += inBuf[o + 1]; r += inBuf[o + 2]; n++;
                            }
                        }
                        int pp = y * stride + x * 4;
                        outBuf[pp] = (byte)(b / n);
                        outBuf[pp + 1] = (byte)(gg / n);
                        outBuf[pp + 2] = (byte)(r / n);
                        outBuf[pp + 3] = 255;
                    }
                }
                Marshal.Copy(outBuf, 0, dd.Scan0, outBuf.Length);
            }
            finally
            {
                src.UnlockBits(sd);
                dst.UnlockBits(dd);
            }
            return dst;
        }

        private string Signature()
        {
            StringBuilder sb = new StringBuilder();
            lock (_lock)
            {
                sb.Append(_devices.Count);
                foreach (MouseDevice d in _devices)
                    sb.Append('|').Append(d.Key).Append(':').Append(d.Battery)
                      .Append(',').Append(d.ActiveStage).Append(',').Append(d.Awake);
            }
            return sb.ToString();
        }

        private void ApplyLayout(int count)
        {
            int width = count <= 0 ? 120 : count * 100 + 24;
            if (ClientSize.Width != width)
            {
                ClientSize = new Size(width, 132);
                using (GraphicsPath rp = RoundPath(new Rectangle(0, 0, width, 132), 22))
                    Region = new Region(rp);
            }
            if (count <= 0)
            {
                if (Visible) Hide();
                return;
            }
            if (!Visible) Show();
            Render();
        }

        private void Render()
        {
            if (!IsHandleCreated || Width <= 0 || Height <= 0) return;
            if (!_drag && (Left != _lastX || Top != _lastY))
            {
                _lastX = Left;
                _lastY = Top;
                _backdropDirty = true;
            }
            if (_backdropDirty || _backdrop == null) CaptureBackdrop();

            using (Bitmap bmp = new Bitmap(Width, Height, System.Drawing.Imaging.PixelFormat.Format32bppArgb))
            {
                using (Graphics g = Graphics.FromImage(bmp))
                {
                    g.SmoothingMode = SmoothingMode.AntiAlias;
                    g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAlias;
                    g.Clear(Color.Transparent);

                    Rectangle full = new Rectangle(0, 0, Width, Height);
                    using (GraphicsPath bgp = RoundPath(full, 22))
                    {
                        if (_backdrop != null)
                        {
                            Region old = g.Clip;
                            g.SetClip(bgp);
                            using (System.Drawing.Imaging.ImageAttributes ia = new System.Drawing.Imaging.ImageAttributes())
                            {
                                System.Drawing.Imaging.ColorMatrix cm = new System.Drawing.Imaging.ColorMatrix();
                                cm.Matrix33 = 0.38f;
                                ia.SetColorMatrix(cm);
                                g.DrawImage(_backdrop, new Rectangle(0, 0, Width, Height),
                                    0, 0, Width, Height, GraphicsUnit.Pixel, ia);
                            }
                            using (SolidBrush tint = new SolidBrush(Color.FromArgb(46, 255, 255, 255)))
                                g.FillPath(tint, bgp);
                            g.Clip = old;
                        }
                        using (Pen border = new Pen(Color.FromArgb(110, 255, 255, 255), 1f))
                            g.DrawPath(border, bgp);
                    }

                    lock (_lock)
                    {
                        int n = Math.Min(_devices.Count, 4);
                        if (n == 0)
                        {
                            using (SolidBrush dim = new SolidBrush(Color.FromArgb(120, 120, 128)))
                                g.DrawString("未发现设备", _fSub, dim, 20, Height / 2 - 9);
                        }
                        else
                        {
                            int slot = Width / n;
                            for (int i = 0; i < n; i++)
                            {
                                MouseDevice d = _devices[i];
                                int cx = slot * i + slot / 2;
                                DrawRing(g, new Rectangle(cx - 26, 22, 52, 52), d);
                                DrawCaption(g, cx, d);
                            }
                        }
                    }
                    DrawPin(g);
                }
                Premultiply(bmp);
                UpdateLayered(bmp);
            }
        }

        private static bool IsMouse(MouseDevice d)
        {
            return d.ProductId == 0x100C || d.ProductId == 0x1021;
        }

        private void DrawRing(Graphics g, Rectangle r, MouseDevice d)
        {
            int pct = d.Battery;
            Color track = Color.FromArgb(110, 255, 255, 255);
            Color fill = !d.Awake ? Color.FromArgb(60, 0, 0, 0)
                       : pct <= 20 ? Color.FromArgb(255, 59, 48)
                       : pct <= 40 ? Color.FromArgb(255, 204, 0)
                       : Color.FromArgb(52, 199, 89);

            using (Pen tp = new Pen(track, 5f))
                g.DrawEllipse(tp, r);
            if (pct > 0)
            {
                using (Pen fp = new Pen(fill, 5f))
                {
                    fp.StartCap = LineCap.Round;
                    fp.EndCap = LineCap.Round;
                    g.DrawArc(fp, r, -90f, 360f * Math.Min(pct, 100) / 100f);
                }
            }

            DrawIcon(g, r, d);

            if (d.Charge == 1)
            {
                PointF[] bolt = new PointF[] {
                    new PointF(r.X + r.Width - 8, r.Y - 2),
                    new PointF(r.X + r.Width - 14, r.Y + 9),
                    new PointF(r.X + r.Width - 9, r.Y + 9),
                    new PointF(r.X + r.Width - 13, r.Y + 20),
                    new PointF(r.X + r.Width - 2, r.Y + 6),
                    new PointF(r.X + r.Width - 7, r.Y + 6)
                };
                using (SolidBrush b = new SolidBrush(Color.FromArgb(52, 199, 89)))
                using (Pen p = new Pen(Color.FromArgb(20, 20, 24), 1.5f))
                {
                    g.FillPolygon(b, bolt);
                    g.DrawPolygon(p, bolt);
                }
            }
        }

        private void DrawIcon(Graphics g, Rectangle r, MouseDevice d)
        {
            Color c = Color.FromArgb(d.Awake ? 200 : 90, 40, 40, 45);
            int cx = r.X + r.Width / 2;
            int cy = r.Y + r.Height / 2;

            using (Pen p = new Pen(c, 1.6f))
            using (SolidBrush b = new SolidBrush(c))
            {
                if (d.ProductId == 0x385D)
                {
                    // headset: headband arc + two earcups
                    g.DrawArc(p, cx - 9, cy - 11, 18, 18, 200, 140);
                    using (GraphicsPath cup = RoundPath(new Rectangle(cx - 11, cy - 1, 6, 9), 2))
                        g.DrawPath(p, cup);
                    using (GraphicsPath cup2 = RoundPath(new Rectangle(cx + 5, cy - 1, 6, 9), 2))
                        g.DrawPath(p, cup2);
                }
                else if (IsMouse(d))
                {
                    // rounded mouse body
                    Rectangle body = new Rectangle(cx - 8, cy - 12, 16, 24);
                    using (GraphicsPath path = RoundPath(body, 8))
                        g.DrawPath(p, path);
                    g.DrawLine(p, cx, cy - 12, cx, cy - 5);
                    g.FillEllipse(b, cx - 1.2f, cy - 8.5f, 2.4f, 2.4f);
                }
                else
                {
                    // keyboard icon
                    Rectangle kb = new Rectangle(cx - 11, cy - 7, 22, 14);
                    using (GraphicsPath path = RoundPath(kb, 3))
                        g.DrawPath(p, path);
                    g.DrawLine(p, kb.X + 4, kb.Y + 5, kb.Right - 4, kb.Y + 5);
                    g.DrawLine(p, kb.X + 5, kb.Y + 9, kb.Right - 5, kb.Y + 9);
                }
            }
        }

        private void DrawCaption(Graphics g, int cx, MouseDevice d)
        {
            string pct = d.Battery >= 0 ? d.Battery + "%" : "--";
            Color pctColor = d.Battery >= 0 ? Color.FromArgb(28, 28, 30) : Color.FromArgb(120, 120, 128);
            using (SolidBrush b = new SolidBrush(pctColor))
            {
                SizeF sz = g.MeasureString(pct, _fPct);
                
                g.DrawString(pct, _fPct, b, cx - sz.Width / 2f, 82);
            }

            if (IsMouse(d) && d.Stages[0] > 0 && d.ActiveStage >= 0 && d.ActiveStage < 6)
            {
                string dpi = string.Format("{0:N0} DPI", d.Stages[d.ActiveStage]);
                using (SolidBrush dim = new SolidBrush(Color.FromArgb(120, 120, 128)))
                {
                    SizeF ds = g.MeasureString(dpi, _fTiny);
                    
                    g.DrawString(dpi, _fTiny, dim, cx - ds.Width / 2f, 112);
                }
            }
        }

        private static void Premultiply(Bitmap bmp)
        {
            System.Drawing.Imaging.BitmapData data = bmp.LockBits(
                new Rectangle(0, 0, bmp.Width, bmp.Height),
                System.Drawing.Imaging.ImageLockMode.ReadWrite,
                System.Drawing.Imaging.PixelFormat.Format32bppArgb);
            try
            {
                int bytes = Math.Abs(data.Stride) * bmp.Height;
                byte[] buf = new byte[bytes];
                Marshal.Copy(data.Scan0, buf, 0, bytes);
                for (int i = 0; i < bytes; i += 4)
                {
                    int a = buf[i + 3];
                    if (a == 255) continue;
                    buf[i] = (byte)(buf[i] * a / 255);
                    buf[i + 1] = (byte)(buf[i + 1] * a / 255);
                    buf[i + 2] = (byte)(buf[i + 2] * a / 255);
                }
                Marshal.Copy(buf, 0, data.Scan0, bytes);
            }
            finally
            {
                bmp.UnlockBits(data);
            }
        }

        private void UpdateLayered(Bitmap bmp)
        {
            IntPtr screenDc = Native.GetDC(IntPtr.Zero);
            IntPtr memDc = Native.CreateCompatibleDC(screenDc);
            IntPtr hBitmap = bmp.GetHbitmap(Color.FromArgb(0));
            IntPtr old = Native.SelectObject(memDc, hBitmap);
            try
            {
                Native.POINT dst = new Native.POINT();
                dst.X = Left;
                dst.Y = Top;
                Native.SIZE size = new Native.SIZE();
                size.cx = bmp.Width;
                size.cy = bmp.Height;
                Native.POINT src = new Native.POINT();
                src.X = 0;
                src.Y = 0;
                Native.BLENDFUNCTION bf = new Native.BLENDFUNCTION();
                bf.BlendOp = 0;
                bf.BlendFlags = 0;
                bf.SourceConstantAlpha = 255;
                bf.AlphaFormat = 1;
                Native.UpdateLayeredWindow(Handle, screenDc, ref dst, ref size, memDc, ref src, 0, ref bf, 2);
            }
            finally
            {
                Native.SelectObject(memDc, old);
                Native.DeleteObject(hBitmap);
                Native.DeleteDC(memDc);
                Native.ReleaseDC(IntPtr.Zero, screenDc);
            }
        }

        protected override void OnHandleCreated(EventArgs e)
        {
            base.OnHandleCreated(e);
            int dark = 1;
            Native.DwmSetWindowAttribute(Handle, 20, ref dark, 4);
            int backdrop = 3;
            int hr = Native.DwmSetWindowAttribute(Handle, 38, ref backdrop, 4);
            int corner = 2;
            Native.DwmSetWindowAttribute(Handle, 33, ref corner, 4);
            Native.MARGINS margins = new Native.MARGINS();
            margins.cxLeftWidth = -1;
            margins.cxRightWidth = -1;
            margins.cyTopHeight = -1;
            margins.cyBottomHeight = -1;
            Native.DwmExtendFrameIntoClientArea(Handle, ref margins);

        }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.Clear(Color.Black);
        }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            if (e.Button == MouseButtons.Left)
            {
                if (PinRect().Contains(e.Location))
                {
                    TogglePin();
                    return;
                }
                if (!_locked)
                {
                    _drag = true;
                    _dragStart = e.Location;
                }
            }
            base.OnMouseDown(e);
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            Cursor = PinRect().Contains(e.Location) ? Cursors.Hand : Cursors.Default;
            if (_drag)
            {
                Point p = PointToScreen(e.Location);
                Location = new Point(p.X - _dragStart.X, p.Y - _dragStart.Y);
                Invalidate();
            }
            base.OnMouseMove(e);
        }

        protected override void OnMouseUp(MouseEventArgs e)
        {
            if (_drag) { SaveState(); _backdropDirty = true; }
            _drag = false;
            base.OnMouseUp(e);
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            SaveState();
            _tray.Visible = false;
            _tray.Dispose();
            base.OnFormClosing(e);
        }
    }

    internal static class Native
    {
        [StructLayout(LayoutKind.Sequential)]
        public struct POINT { public int X; public int Y; }

        [StructLayout(LayoutKind.Sequential)]
        public struct SIZE { public int cx; public int cy; }

        [StructLayout(LayoutKind.Sequential, Pack = 1)]
        public struct BLENDFUNCTION
        {
            public byte BlendOp;
            public byte BlendFlags;
            public byte SourceConstantAlpha;
            public byte AlphaFormat;
        }

        [DllImport("user32.dll", SetLastError = true)]
        public static extern bool UpdateLayeredWindow(IntPtr hwnd, IntPtr hdcDst,
            ref POINT pptDst, ref SIZE psize, IntPtr hdcSrc, ref POINT pptSrc,
            int crKey, ref BLENDFUNCTION pblend, int dwFlags);

        [DllImport("user32.dll")]
        public static extern IntPtr GetDC(IntPtr hWnd);

        [DllImport("user32.dll")]
        public static extern int ReleaseDC(IntPtr hWnd, IntPtr hDC);

        [DllImport("gdi32.dll")]
        public static extern IntPtr CreateCompatibleDC(IntPtr hdc);

        [DllImport("gdi32.dll")]
        public static extern bool DeleteDC(IntPtr hdc);

        [DllImport("gdi32.dll")]
        public static extern IntPtr SelectObject(IntPtr hdc, IntPtr h);

        [DllImport("gdi32.dll")]
        public static extern bool DeleteObject(IntPtr o);

        [DllImport("user32.dll")]
        public static extern bool SetProcessDPIAware();

        [StructLayout(LayoutKind.Sequential)]
        public struct MARGINS
        {
            public int cxLeftWidth;
            public int cxRightWidth;
            public int cyTopHeight;
            public int cyBottomHeight;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct AccentPolicy
        {
            public int AccentState;
            public int AccentFlags;
            public int GradientColor;
            public int AnimationId;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct WindowCompositionAttributeData
        {
            public int Attribute;
            public IntPtr Data;
            public int SizeOfData;
        }

        [DllImport("dwmapi.dll")]
        public static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int value, int size);

        [DllImport("dwmapi.dll")]
        public static extern int DwmExtendFrameIntoClientArea(IntPtr hwnd, ref MARGINS margins);

        [DllImport("user32.dll")]
        public static extern int SetWindowCompositionAttribute(IntPtr hwnd, ref WindowCompositionAttributeData data);

        [DllImport("user32.dll")]
        public static extern bool SetLayeredWindowAttributes(IntPtr hwnd, uint colorKey, byte alpha, uint flags);

        [DllImport("user32.dll")]
        public static extern bool ShowWindow(IntPtr hwnd, int cmd);

        [StructLayout(LayoutKind.Sequential)]
        public struct OVERLAPPED
        {
            public IntPtr Internal;
            public IntPtr InternalHigh;
            public int Offset;
            public int OffsetHigh;
            public IntPtr hEvent;
        }

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        public static extern IntPtr CreateEvent(IntPtr attrs, bool manualReset, bool initialState, string name);

        [DllImport("kernel32.dll", SetLastError = true)]
        public static extern bool ReadFile(IntPtr h, byte[] buffer, int count, out uint read, ref OVERLAPPED ov);

        [DllImport("kernel32.dll", SetLastError = true)]
        public static extern bool WriteFile(IntPtr h, byte[] buffer, int count, out uint written, ref OVERLAPPED ov);

        [DllImport("kernel32.dll")]
        public static extern uint WaitForSingleObject(IntPtr h, uint ms);

        [DllImport("kernel32.dll")]
        public static extern bool GetOverlappedResult(IntPtr h, ref OVERLAPPED ov, out uint transferred, bool wait);

        public static void EnableAcrylic(IntPtr hwnd, uint tint)
        {
            AccentPolicy policy = new AccentPolicy();
            policy.AccentState = 4;
            policy.AccentFlags = 2;
            policy.GradientColor = unchecked((int)tint);
            WindowCompositionAttributeData data = new WindowCompositionAttributeData();
            data.Attribute = 19;
            data.SizeOfData = Marshal.SizeOf(typeof(AccentPolicy));
            data.Data = Marshal.AllocHGlobal(data.SizeOfData);
            try
            {
                Marshal.StructureToPtr(policy, data.Data, false);
                SetWindowCompositionAttribute(hwnd, ref data);
            }
            finally
            {
                Marshal.FreeHGlobal(data.Data);
            }
        }
    }

    internal static class Startup
    {
        private const string RunKey = @"Software\Microsoft\Windows\CurrentVersion\Run";
        private const string RunName = "MCHOSE Widget";

        public static bool IsEnabled()
        {
            try
            {
                using (RegistryKey k = Registry.CurrentUser.OpenSubKey(RunKey))
                {
                    if (k == null) return false;
                    object v = k.GetValue(RunName);
                    return v != null && v.ToString().Trim() == "\"" + Application.ExecutablePath + "\"";
                }
            }
            catch { return false; }
        }

        public static void Set(bool on)
        {
            try
            {
                using (RegistryKey k = Registry.CurrentUser.CreateSubKey(RunKey))
                {
                    if (k == null) return;
                    if (on) k.SetValue(RunName, "\"" + Application.ExecutablePath + "\"");
                    else k.DeleteValue(RunName, false);
                }
            }
            catch { }
        }
    }

    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            string[] cli = Environment.GetCommandLineArgs();
            if (cli.Length > 1)
            {
                if (cli[1] == "--autostart=on") { Startup.Set(true); return; }
                if (cli[1] == "--autostart=off") { Startup.Set(false); return; }
            }
            Native.SetProcessDPIAware();
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new Widget());
        }
    }
}
