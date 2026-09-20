"""Exercise the real Windows launcher, without opening the app or any user library."""
import base64
import os
from pathlib import Path
import subprocess
import time

import pytest

from build_nuitka import build_launcher_stub, find_csc


@pytest.mark.skipif(os.name != 'nt', reason='Windows launcher')
def test_launcher_forwards_exact_arguments(tmp_path):
    compiler = find_csc()
    if not compiler:
        pytest.skip('C# compiler unavailable')
    release = tmp_path / '程序 空格'
    core = release / 'bin'
    core.mkdir(parents=True)
    receiver = tmp_path / 'receiver.cs'
    receiver.write_text('''
using System;
using System.IO;
using System.Text;
class Receiver {
    static void Main(string[] args) {
        string target = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "received.txt");
        File.WriteAllLines(target + ".tmp", Array.ConvertAll(args,
            arg => Convert.ToBase64String(Encoding.UTF8.GetBytes(arg))));
        File.Move(target + ".tmp", target);
    }
}
''', encoding='utf-8')
    subprocess.run([compiler, '/nologo', '/target:exe',
                    '/out:' + str(core / 'NekoriEmojy.exe'), str(receiver)],
                   check=True, capture_output=True)
    launcher = build_launcher_stub(release)
    arguments = ['--library', str(tmp_path / '图库 中文 😀') + '\\',
                 '', 'ordinary', 'a"b', 'a\\\\"b', 'two words\\\\']
    subprocess.run([launcher, *arguments], cwd=tmp_path, check=True, timeout=10)
    report = core / 'received.txt'
    deadline = time.monotonic() + 10
    while not report.exists() and time.monotonic() < deadline:
        time.sleep(.02)
    assert report.exists(), 'core did not start'
    received = [base64.b64decode(line).decode('utf-8')
                for line in report.read_text(encoding='utf-8-sig').splitlines()]
    assert received == arguments
