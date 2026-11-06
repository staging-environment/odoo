# =========================================================================
# UTRECAR - CENTINELA EN TIEMPO REAL TPV 2 (RONDA NORTE)
# Monitoriza la respuesta de la GUI, memoria, red y logs de VirtusTPVNet
# Envia alertas instantaneas a Telegram ante cualquier congelacion
# Auto-recupera memoria mediante EmptyWorkingSet sin tocar servicios
# =========================================================================

$ErrorActionPreference = "Continue"

$BotToken = "8637497198:AAGJWp6cwDBu0CeTLkDVd-0nanl1ZtXFbjg"
$ChatId   = "5914920849"
$TPV1_IP  = "192.168.1.20"

$LogFile  = "C:\Utrecar\centinela.log"
$ActLog   = "C:\Program Files\Aseproda\VirtusTPV Net\Actividad.Log"

# Compilador de MemoryManager nativo para purga en caliente
$typeDef = @"
using System;
using System.Runtime.InteropServices;
public class MemoryManager {
    [DllImport("psapi.dll")]
    public static extern int EmptyWorkingSet(IntPtr hwProc);
}
"@
if (-not ([System.Management.Automation.PSTypeName]'MemoryManager').Type) {
    Add-Type -TypeDefinition $typeDef -Language CSharp
}

function Write-CentinelaLog([string]$msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    Add-Content -Path $LogFile -Value $line -ErrorAction SilentlyContinue
}

function Send-Telegram([string]$msg) {
    try {
        $url = "https://api.telegram.org/bot" + $BotToken + "/sendMessage"
        curl.exe -s -X POST $url -d "chat_id=$ChatId" -d "text=$msg" | Out-Null
        Write-CentinelaLog "Alerta Telegram enviada."
    } catch {
        Write-CentinelaLog "Error enviando alerta Telegram: $_"
    }
}

Write-CentinelaLog "Iniciando Centinela TPV 2 Ronda Norte..."

$isFrozen = $false
$freezeStartTime = $null
$lastAutoTrim = [DateTime]::MinValue

while ($true) {
    try {
        $p = Get-Process -Name VirtusTPVNet -ErrorAction SilentlyContinue

        if (-not $p) {
            Write-CentinelaLog "VirtusTPVNet no esta en ejecucion."
            Start-Sleep -Seconds 3
            continue
        }

        # 1. Comprobar si la interfaz de usuario esta CONGELADA
        if (-not $p.Responding) {
            if (-not $isFrozen) {
                $isFrozen = $true
                $freezeStartTime = Get-Date

                $memMB = [math]::Round($p.WorkingSet64 / 1MB, 1)
                $memGB = [math]::Round($p.WorkingSet64 / 1GB, 2)

                # Comprobacion de sockets con TPV 1
                $mysqlOk = (Test-NetConnection -ComputerName $TPV1_IP -Port 3306 -WarningAction SilentlyContinue).TcpTestSucceeded
                $sdesOk  = (Test-NetConnection -ComputerName $TPV1_IP -Port 8777 -WarningAction SilentlyContinue).TcpTestSucceeded

                $mysqlStatus = if ($mysqlOk) { "CONECTADO (OK)" } else { "CAIDO / MICRO-CORTE" }
                $sdesStatus  = if ($sdesOk)  { "CONECTADO (OK)" } else { "CAIDO / ERROR" }

                # Ultimas lineas de Actividad.Log
                $lastActivity = ""
                if (Test-Path $ActLog) {
                    $lines = Get-Content -Path $ActLog -Tail 5 -ErrorAction SilentlyContinue
                    $lastActivity = $lines -join "`n"
                }

                $nowStr = Get-Date -Format "HH:mm:ss"
                $alertText = "[ALERTA: TPV 2 CONGELADO / NO RESPONDE]`n`n" +
                             "Estacion: E.S. Ronda Norte (Cod. 2)`n" +
                             "Hora deteccion: " + $nowStr + "`n" +
                             "Memoria RAM: " + $memGB + " GB (" + $memMB + " MB)`n" +
                             "Conexion MySQL TPV1 (3306): " + $mysqlStatus + "`n" +
                             "Conexion SDES Pista (8777): " + $sdesStatus + "`n`n" +
                             "Ultima actividad registrada:`n" + $lastActivity

                Write-CentinelaLog "BLOQUEO DETECTADO. Enviando alerta Telegram..."
                Send-Telegram $alertText
            }
        } else {
            # Si estaba congelado y acaba de recuperar respuesta
            if ($isFrozen) {
                $duration = [math]::Round(((Get-Date) - $freezeStartTime).TotalSeconds, 1)
                $isFrozen = $false
                $recTime = Get-Date -Format "HH:mm:ss"

                $recoveryText = "[TPV 2 HA RECUPERADO LA RESPUESTA]`n`n" +
                                "Duracion del bloqueo: " + $duration + " segundos`n" +
                                "Hora recuperacion: " + $recTime

                Write-CentinelaLog "RECUPERADO tras $duration s."
                Send-Telegram $recoveryText
            }
        }

        # 2. Auto-recuperacion preventiva de memoria si supera 600 MB (Sin afectar al cajero)
        $memMB2 = $p.WorkingSet64 / 1MB
        if ($memMB2 -gt 600 -and ((Get-Date) - $lastAutoTrim).TotalMinutes -ge 15) {
            $lastAutoTrim = Get-Date
            $beforeTrim = [math]::Round($memMB2, 1)
            [MemoryManager]::EmptyWorkingSet($p.Handle) | Out-Null
            Start-Sleep -Milliseconds 500
            $afterTrim = [math]::Round((Get-Process -Id $p.Id).WorkingSet64 / 1MB, 1)
            $freed = [math]::Round($beforeTrim - $afterTrim, 1)

            Write-CentinelaLog "Auto-purga preventiva: $beforeTrim MB -> $afterTrim MB (Liberados: $freed MB)"
        }

    } catch {
        Write-CentinelaLog "Excepcion en centinela: $_"
    }

    Start-Sleep -Seconds 2
}
