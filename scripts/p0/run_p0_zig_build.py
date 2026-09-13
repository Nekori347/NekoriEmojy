"""Execute the original P0 recipe with an explicit supported C compiler.

Product and upstream recipe files remain byte-for-byte unchanged. The command
adapter adds --zig and --jobs=4 only to Nuitka, and prints the effective command.
This is a bounded baseline experiment, not the NekoriEmojy release builder.
"""
import runpy
import subprocess
from unittest.mock import patch

original_popen = subprocess.Popen


def with_explicit_compiler(args, *positional, **kwargs):
    if isinstance(args, list) and len(args) > 3 and args[1:3] == ["-m", "nuitka"]:
        args = args[:-1] + ["--zig", "--jobs=4"] + args[-1:]
        print("P0 effective compiler command:", subprocess.list2cmdline(args), flush=True)
    return original_popen(args, *positional, **kwargs)


with patch.object(subprocess, "Popen", with_explicit_compiler):
    runpy.run_path("build_nuitka.py", run_name="__main__")
