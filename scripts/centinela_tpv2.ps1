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

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Send-Telegram([string]$msg) {
    $sent = $false
    try {
        $url = "https://api.telegram.org/bot$BotToken/sendMessage"
        $payload = @{
            chat_id = $ChatId
            text    = $msg
        } | ConvertTo-Json -Compress
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
        $resp = Invoke-RestMethod -Uri $url -Method Post -Body $bytes -ContentType "application/json; charset=utf-8" -TimeoutSec 10
        if ($resp.ok) {
            $sent = $true
            Write-CentinelaLog "Alerta Telegram enviada directamente a Jose ($ChatId)."
        }
    } catch {
        Write-CentinelaLog "Error envio directo Telegram, probando pasarela Odoo: $_"
    }

    if (-not $sent) {
        try {
            $odooUrl = "https://odoo.utrecar.com/pos_gas_station/centinela_alert"
            $payload = @{ text = $msg } | ConvertTo-Json -Compress
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
            Invoke-RestMethod -Uri $odooUrl -Method Post -Body $bytes -ContentType "application/json; charset=utf-8" -TimeoutSec 10 | Out-Null
            Write-CentinelaLog "Alerta Telegram enviada via pasarela Odoo a Jose."
        } catch {
            Write-CentinelaLog "Error enviando alerta via pasarela Odoo: $_"
        }
    }
}

function Test-TcpFast([string]$ip, [int]$port, [int]$timeoutMs = 1200) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($ip, $port, $null, $null)
        $wait = $iar.AsyncWaitHandle.WaitOne($timeoutMs, $false)
        if (-not $wait) {
            $client.Close()
            return $false
        }
        $client.EndConnect($iar)
        $client.Close()
        return $true
    } catch {
        $client.Close()
        return $false
    }
}

Write-CentinelaLog "Iniciando Centinela TPV 2 Ronda Norte..."
Send-Telegram "hola hola (Centinela TPV 2 Ronda Norte activo y monitorizando cada 2s)"

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

        # Comprobacion rapida de conexion TCP con TPV 1 (MySQL 3306 y SDES 8777) y estado de GUI
        $guiResponding = $p.Responding
        $mysqlOk = Test-TcpFast $TPV1_IP 3306 1200
        $sdesOk  = Test-TcpFast $TPV1_IP 8777 1200

        # 1. Detectar si la pantalla se congela O si cae/congela la conexion con TPV 1
        if ((-not $guiResponding) -or (-not $mysqlOk) -or (-not $sdesOk)) {
            if (-not $isFrozen) {
                $isFrozen = $true
                $freezeStartTime = Get-Date

                $memMB = [math]::Round($p.WorkingSet64 / 1MB, 1)
                $memGB = [math]::Round($p.WorkingSet64 / 1GB, 2)

                $guiStatus   = if ($guiResponding) { "RESPONDIENDO (OK)" } else { "CONGELADA (NO RESPONDE)" }
                $mysqlStatus = if ($mysqlOk) { "CONECTADO (OK)" } else { "CAIDO / TIMEOUT (>1.2s)" }
                $sdesStatus  = if ($sdesOk)  { "CONECTADO (OK)" } else { "CAIDO / TIMEOUT (>1.2s)" }

                # Elaborar diagnostico automatico de lo que esta pasando
                $diagList = @()
                if (-not $mysqlOk -and -not $sdesOk) {
                    $diagList += "- Corte total de red LAN entre TPV 2 (192.168.1.64) y TPV 1 (192.168.1.20)."
                } elseif (-not $mysqlOk) {
                    $diagList += "- Fallo/saturacion del motor MySQL (puerto 3306) en TPV 1."
                } elseif (-not $sdesOk) {
                    $diagList += "- Perdida de conexion con el concentrador de pista SDES (puerto 8777) en TPV 1."
                }
                if (-not $guiResponding -and $mysqlOk -and $sdesOk) {
                    $diagList += "- Bloqueo sincrono de VirtusTPV esperando respuesta SQL de TPV 1 (posible colision de serie compartida TTRN/FTRN o lock de tabla en MySQL) o espera de cola de impresion WSD."
                }
                if ($memMB -gt 600) {
                    $diagList += "- Memoria RAM elevada en VirtusTPVNet ($memMB MB)."
                }
                $diagnostico = $diagList -join "`n"

                # Ultimas lineas de Actividad.Log
                $lastActivity = ""
                if (Test-Path $ActLog) {
                    $lines = Get-Content -Path $ActLog -Tail 5 -ErrorAction SilentlyContinue
                    $lastActivity = $lines -join "`n"
                }

                $nowStr = Get-Date -Format "HH:mm:ss"
                $alertText = "[ALERTA CENTINELA: CONGELACION DETECTADA EN TPV 2]`n`n" +
                             "Estacion: E.S. Ronda Norte (Cod. 2)`n" +
                             "Hora deteccion: " + $nowStr + "`n" +
                             "Estado Pantalla GUI: " + $guiStatus + "`n" +
                             "Conexion MySQL TPV1 (3306): " + $mysqlStatus + "`n" +
                             "Conexion SDES Pista (8777): " + $sdesStatus + "`n" +
                             "Memoria RAM VirtusTPV: " + $memGB + " GB (" + $memMB + " MB)`n`n" +
                             "DIAGNOSTICO PROBABLE:`n" + $diagnostico + "`n`n" +
                             "Ultima actividad en log:`n" + $lastActivity

                Write-CentinelaLog "INCIDENCIA DETECTADA. Enviando alerta Telegram a Jose..."
                Send-Telegram $alertText
            }
        } else {
            # Si estaba congelado/caido y acaba de recuperar respuesta y conexion
            if ($isFrozen) {
                $duration = [math]::Round(((Get-Date) - $freezeStartTime).TotalSeconds, 1)
                $isFrozen = $false
                $recTime = Get-Date -Format "HH:mm:ss"

                $recoveryText = "[TPV 2 RONDA NORTE RECUPERADO]`n`n" +
                                "Duracion de la incidencia: " + $duration + " segundos`n" +
                                "Hora recuperacion: " + $recTime + "`n" +
                                "Estado actual: Pantalla OK | MySQL 3306 OK | SDES 8777 OK"

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
