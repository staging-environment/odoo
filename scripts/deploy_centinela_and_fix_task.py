#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import os
import subprocess
import sys

def run_remote_ps(host, ps_code):
    b64 = base64.b64encode(ps_code.encode("utf-16le")).decode()
    cmd = ["ssh", host, f"powershell.exe -NoProfile -NonInteractive -EncodedCommand {b64}"]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
    return res.stdout.decode("cp1252", errors="replace"), res.stderr.decode("cp1252", errors="replace")

def copy_file_to_remote(host, local_path, remote_path):
    with open(local_path, "rb") as f:
        data = f.read()
    b64_content = base64.b64encode(data).decode()
    ps_cmd = f"""
    $dir = Split-Path -Path '{remote_path}'
    if (-not (Test-Path $dir)) {{ New-Item -ItemType Directory -Path $dir -Force | Out-Null }}
    $bytes = [Convert]::FromBase64String('{b64_content}')
    [IO.File]::WriteAllBytes('{remote_path}', $bytes)
    Test-Path '{remote_path}'
    """
    out, err = run_remote_ps(host, ps_cmd)
    return "True" in out

def main():
    print("=== 1. Corrigiendo Tarea de Reciclaje de 04:00 AM en TPV 1 y TPV 2 ===")
    fix_task_code = r"""
    $bat = "C:\Utrecar\reciclar_virtustpv.bat"
    if (Test-Path $bat) {
        schtasks /Delete /TN "ReciclajeVirtusTPV" /F 2>$null | Out-Null
        schtasks /Create /TN "ReciclajeVirtusTPV" /TR $bat /SC DAILY /ST 04:00 /RU "SYSTEM" /F | Out-Null
        $t = Get-ScheduledTask -TaskName "ReciclajeVirtusTPV" -ErrorAction SilentlyContinue
        "ReciclajeVirtusTPV: " + $t.Actions.Execute + " [Next: " + (Get-ScheduledTaskInfo -TaskName "ReciclajeVirtusTPV").NextRunTime + "]"
    } else {
        "Archivo " + $bat + " no encontrado"
    }
    """
    for host in ["rondanorte", "rondanorte-tpv2"]:
        out, _ = run_remote_ps(host, fix_task_code)
        print(f"[{host}] {out.strip()}")

    print("\n=== 2. Copiando Centinela a TPV 2 ===")
    local_script = os.path.join(os.path.dirname(__file__), "centinela_tpv2.ps1")
    remote_script = r"C:\Utrecar\centinela_tpv2.ps1"
    ok = copy_file_to_remote("rondanorte-tpv2", local_script, remote_script)
    print(f"Copiado a {remote_script}: {ok}")

    print("\n=== 3. Creando y Arrancando Servicio Centinela en TPV 2 ===")
    setup_centinela = r"""
    # Detener proceso previo si existiera
    Get-Process powershell -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*centinela_tpv2.ps1*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    
    # Crear tarea para arranque automático al iniciar Windows
    $taskName = "CentinelaTPV2"
    $script = "C:\Utrecar\centinela_tpv2.ps1"
    $action = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
    schtasks /Delete /TN $taskName /F 2>$null | Out-Null
    schtasks /Create /TN $taskName /TR $action /SC ONSTART /RU "SYSTEM" /F | Out-Null

    # Arrancar tarea de inmediato en segundo plano
    schtasks /Run /TN $taskName | Out-Null
    Start-Sleep -Seconds 3

    # Comprobar si está corriendo
    $proc = Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" | Where-Object { $_.CommandLine -like "*centinela_tpv2.ps1*" }
    if ($proc) {
        "CENTINELA_CORRIENDO PID: " + $proc.ProcessId
    } else {
        # Arrancar directamente con Start-Process en segundo plano si la tarea schtasks tarda
        Start-Process powershell.exe -ArgumentList "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`"" -WindowStyle Hidden
        Start-Sleep -Seconds 2
        $proc2 = Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" | Where-Object { $_.CommandLine -like "*centinela_tpv2.ps1*" }
        if ($proc2) { "CENTINELA_CORRIENDO PID: " + $proc2.ProcessId } else { "ERROR ARRANCANDO" }
    }
    """
    out, err = run_remote_ps("rondanorte-tpv2", setup_centinela)
    print(f"[rondanorte-tpv2] {out.strip()}")
    if err and not err.startswith("#< CLIXML"):
        print(f"ERR: {err}")

if __name__ == "__main__":
    main()
