#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import subprocess
import sys

def run_ps(host, ps_code):
    b64 = base64.b64encode(ps_code.encode("utf-16le")).decode()
    cmd = ["ssh", host, f"powershell.exe -NoProfile -NonInteractive -EncodedCommand {b64}"]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
    stdout = res.stdout.decode("cp1252", errors="replace")
    stderr = res.stderr.decode("cp1252", errors="replace")
    return stdout, stderr

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "rondanorte-tpv2"
    code = sys.argv[2] if len(sys.argv) > 2 else "Get-Process VirtusTPVNet | Format-List Id, ProcessName, Path, WorkingSet64"
    out, err = run_ps(host, code)
    print("STDOUT:")
    print(out)
    if err and not err.startswith("#< CLIXML"):
        print("STDERR:")
        print(err)
