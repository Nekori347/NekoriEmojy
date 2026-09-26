using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;

internal static class LauncherStub
{
    [STAThread]
    private static void Main(string[] args)
    {
        string baseDirectory = AppDomain.CurrentDomain.BaseDirectory;
        string targetPath = Path.Combine(baseDirectory, "bin", "NekoriEmojy.exe");

        if (!File.Exists(targetPath))
        {
            MessageBox.Show(
                "找不到核心程序：" + Environment.NewLine + targetPath + Environment.NewLine + Environment.NewLine +
                "请确保 bin 文件夹完整。",
                "NekoriEmojy",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return;
        }

        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = targetPath,
                Arguments = string.Join(" ", Array.ConvertAll(args, QuoteArgument)),
                WorkingDirectory = baseDirectory,
                UseShellExecute = false,
                CreateNoWindow = true
            });
        }
        catch (Exception error)
        {
            MessageBox.Show(
                "启动核心程序失败：" + Environment.NewLine + error.Message,
                "NekoriEmojy",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    // ProcessStartInfo on .NET Framework accepts one command line. Preserve
    // empty arguments, quotes and trailing backslashes under Windows argv rules.
    private static string QuoteArgument(string value)
    {
        StringBuilder quoted = new StringBuilder("\"");
        int slashes = 0;
        foreach (char ch in value)
        {
            if (ch == '\\')
            {
                slashes++;
                continue;
            }
            quoted.Append('\\', ch == '"' ? slashes * 2 + 1 : slashes);
            quoted.Append(ch);
            slashes = 0;
        }
        quoted.Append('\\', slashes * 2);
        quoted.Append('"');
        return quoted.ToString();
    }
}
