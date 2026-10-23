import io

p = r"D:\work\qd\src\MchoseWidget.cs"
s = io.open(p, "r", encoding="utf-8").read()

start = s.index("        private bool IsAutoStart()")
end = s.index("        private Point LoadPosition()")
s = s[:start] + s[end:]

s = s.replace("_miStartup.Checked = IsAutoStart();", "_miStartup.Checked = Startup.IsEnabled();")
s = s.replace("_miStartup.CheckedChanged += delegate { SetAutoStart(_miStartup.Checked); };",
              "_miStartup.CheckedChanged += delegate { Startup.Set(_miStartup.Checked); };")

startup_class = '''    internal static class Startup
    {
        private const string RunKey = @"Software\\Microsoft\\Windows\\CurrentVersion\\Run";
        private const string RunName = "MCHOSE Widget";

        public static bool IsEnabled()
        {
            try
            {
                using (RegistryKey k = Registry.CurrentUser.OpenSubKey(RunKey))
                {
                    if (k == null) return false;
                    object v = k.GetValue(RunName);
                    return v != null && v.ToString().Trim() == "\\"" + Application.ExecutablePath + "\\"";
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
                    if (on) k.SetValue(RunName, "\\"" + Application.ExecutablePath + "\\"");
                    else k.DeleteValue(RunName, false);
                }
            }
            catch { }
        }
    }

'''

if "internal static class Startup" not in s:
    s = s.replace("    internal static class Program", startup_class + "    internal static class Program")

cli = '''        private static void Main()
        {
            string[] cli = Environment.GetCommandLineArgs();
            if (cli.Length > 1)
            {
                if (cli[1] == "--autostart=on") { Startup.Set(true); return; }
                if (cli[1] == "--autostart=off") { Startup.Set(false); return; }
            }
            Native.SetProcessDPIAware();'''

if "--autostart=on" not in s:
    s = s.replace('''        private static void Main()
        {
            Native.SetProcessDPIAware();''', cli)

io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("patched")
