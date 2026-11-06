import sys
sys.path.append('scripts')
import diag_ronda

code = """
$typeDef = @"
using System;
using System.Runtime.InteropServices;
public class MemoryManager {
    [DllImport("psapi.dll")]
    public static extern int EmptyWorkingSet(IntPtr hwProc);
}
"@
Add-Type -TypeDefinition $typeDef -Language CSharp

$p = Get-Process -Name "VirtusTPVNet" -ErrorAction SilentlyContinue
if ($p) {
    $before = [math]::Round($p.WorkingSet64 / 1MB, 1)
    [MemoryManager]::EmptyWorkingSet($p.Handle) | Out-Null
    Start-Sleep -Seconds 1
    $p2 = Get-Process -Id $p.Id
    $after = [math]::Round($p2.WorkingSet64 / 1MB, 1)
    $diff = [math]::Round($before - $after, 1)
    Write-Output ("VirtusTPVNet (PID " + $p.Id + "): Antes: " + $before + " MB -> Despues: " + $after + " MB (Liberados: " + $diff + " MB) | Responding: " + $p2.Responding)
} else {
    Write-Output "VirtusTPVNet no encontrado."
}
"""

out, err = diag_ronda.run_ps('rondanorte-tpv2', code)
print(out)
if err and not err.startswith("#< CLIXML"):
    print("ERR:", err)
