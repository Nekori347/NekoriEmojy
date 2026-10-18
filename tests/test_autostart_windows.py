"""Real HKCU, confined to temporary NON-startup keys; no user's Run writes.

Approval-state cases follow Suzu dc14f4a1f5 (GPL-3.0), adapted for Nekori.
"""
import os,uuid,unittest
from unittest.mock import patch
from services.autostart import AutostartService


@unittest.skipUnless(os.name=='nt','Windows registry')
class WindowsAutostartTests(unittest.TestCase):
    def setUp(self):
        import winreg
        self.reg=winreg;self.service=AutostartService()
        self.root=r'Software\NekoriEmojy\AutostartTests'+chr(92)+uuid.uuid4().hex
        self.service.RUN_KEY=self.root+r'\Run'
        self.service.APPROVAL_KEYS=(self.root+r'\Approval',self.root+r'\Approval32')
        self.command=patch.object(self.service,'command',return_value='"C:\\中文 空格\\SuzuEmojy.exe" --autostart')
        self.command.start();self.addCleanup(self.command.stop);self.addCleanup(self.cleanup)

    def cleanup(self):
        for key in (self.service.RUN_KEY,)+self.service.APPROVAL_KEYS+(self.root,):
            try:self.reg.DeleteKey(self.reg.HKEY_CURRENT_USER,key)
            except FileNotFoundError:pass

    def put(self,path,value,name='NekoriEmojy'):
        with self.reg.CreateKeyEx(self.reg.HKEY_CURRENT_USER,path) as key:
            self.reg.SetValueEx(key,name,0,self.reg.REG_BINARY,value)

    def test_enabled_disabled_and_moved_path_use_real_registry(self):
        self.service.set_enabled(True);self.assertTrue(self.service.is_enabled())
        with patch.object(self.service,'command',return_value='"D:\\新 位置\\SuzuEmojy.exe" --autostart'):
            self.assertFalse(self.service.is_enabled())
            self.service.set_enabled(True);self.assertTrue(self.service.is_enabled())
        self.service.set_enabled(False);self.assertFalse(self.service.is_enabled())
        self.service.set_enabled(False)

    def test_system_disabled_requires_explicit_enable_and_keeps_other_values(self):
        self.service._write_command(self.service.command())
        for key,state in zip(self.service.APPROVAL_KEYS,(3,7)):
            self.put(key,bytes([state])+b'\0'*11)
            self.put(key,b'other-app','OtherApp')
        self.assertFalse(self.service.is_enabled())
        for key in self.service.APPROVAL_KEYS:
            with self.reg.OpenKey(self.reg.HKEY_CURRENT_USER,key) as handle:
                self.assertIn(self.reg.QueryValueEx(handle,'NekoriEmojy')[0][0],(3,7))
        self.service.set_enabled(True);self.assertTrue(self.service.is_enabled())
        for key in self.service.APPROVAL_KEYS:
            with self.reg.OpenKey(self.reg.HKEY_CURRENT_USER,key) as handle:
                self.assertEqual(self.reg.QueryValueEx(handle,'OtherApp')[0],b'other-app')
                with self.assertRaises(FileNotFoundError):self.reg.QueryValueEx(handle,'NekoriEmojy')

    def test_enabled_approval_is_preserved(self):
        for key,state in zip(self.service.APPROVAL_KEYS,(2,6)):self.put(key,bytes([state])+b'\0'*11)
        self.service.set_enabled(True)
        for key,state in zip(self.service.APPROVAL_KEYS,(2,6)):
            with self.reg.OpenKey(self.reg.HKEY_CURRENT_USER,key) as handle:
                self.assertEqual(self.reg.QueryValueEx(handle,'NekoriEmojy')[0][0],state)


@unittest.skipUnless(os.name=='nt','Windows launcher')
class WindowsLauncherTests(unittest.TestCase):
    def test_compiled_launcher_preserves_arguments_and_working_directory(self):
        import base64, subprocess, tempfile, time
        from pathlib import Path
        from build_nuitka import build_launcher_stub, find_csc
        with tempfile.TemporaryDirectory(prefix='Nekori 中文 启动 ') as folder:
            root=Path(folder);(root/'bin').mkdir()
            launcher=build_launcher_stub(str(root))
            marker=root/'marker.cs'
            marker.write_text('''using System; using System.IO; using System.Text;
class Marker { static void Main(string[] args) {
    string[] lines=new string[args.Length+1];
    lines[0]=Convert.ToBase64String(Encoding.UTF8.GetBytes(Environment.CurrentDirectory));
    for(int i=0;i<args.Length;i++) lines[i+1]=Convert.ToBase64String(Encoding.UTF8.GetBytes(args[i]));
    File.WriteAllLines(Path.Combine(Environment.CurrentDirectory,"args.txt"),lines);
} }''',encoding='utf-8')
            subprocess.run([find_csc(),'/nologo','/target:winexe','/out:'+str(root/'bin/SuzuEmojy.exe'),str(marker)],check=True,capture_output=True)
            args=['--autostart','中文 空格','','含"引号','C:'+chr(92)+'结尾 空格'+chr(92)]
            subprocess.run([launcher]+args,cwd=Path(folder).parent,check=True,timeout=10)
            deadline=time.monotonic()+10
            while not (root/'args.txt').exists() and time.monotonic()<deadline:time.sleep(.05)
            lines=(root/'args.txt').read_text('utf-8-sig').splitlines()
            decoded=[base64.b64decode(line).decode('utf-8') for line in lines]
            self.assertEqual(Path(decoded[0]),root)
            self.assertEqual(decoded[1:],args)
