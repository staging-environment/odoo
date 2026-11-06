$ErrorActionPreference = "SilentlyContinue"

$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3"
$v = Get-Process VirtusTPVNet -ErrorAction SilentlyContinue

$uptime = (New-TimeSpan -Start $os.LastBootUpTime -End (Get-Date))
$uptimeStr = "$($uptime.Days) dias, $($uptime.Hours) horas, $($uptime.Minutes) minutos"

$totalRam = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
$freeRam = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
$usedRam = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1MB, 2)
$usedRamPct = [math]::Round((($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize) * 100, 1)

$topRam = Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 6 ProcessName, Id, @{N='RAM_MB';E={[math]::Round($_.WorkingSet64/1MB,1)}}
$topCpu = Get-Process | Sort-Object CPU -Descending | Select-Object -First 6 ProcessName, Id, @{N='CPU_Sec';E={[math]::Round($_.CPU,1)}}, @{N='RAM_MB';E={[math]::Round($_.WorkingSet64/1MB,1)}}

$mysqlTest = Test-NetConnection -ComputerName 192.168.1.20 -Port 3306 -WarningAction SilentlyContinue
$sdesTest = Test-NetConnection -ComputerName 192.168.1.20 -Port 8777 -WarningAction SilentlyContinue

Write-Output "=== RESUMEN GENERAL DEL EQUIPO (MADIC-TPV-IOT) ==="
Write-Output "Tiempo Encendido (Uptime) : $uptimeStr"
Write-Output "Modelo Procesador         : $($cpu.Name)"
Write-Output "Nucleos / Hilos CPU       : $($cpu.NumberOfCores) nucleos / $($cpu.NumberOfLogicalProcessors) hilos"
Write-Output "Carga Actual CPU (WMI)    : $($cpu.LoadPercentage) %"
Write-Output ""
Write-Output "=== ESTADO DE MEMORIA RAM ==="
Write-Output "Memoria RAM Total         : $totalRam GB"
Write-Output "Memoria RAM en Uso        : $usedRam GB ($usedRamPct %)"
Write-Output "Memoria RAM Libre         : $freeRam GB"
Write-Output ""
Write-Output "=== ESTADO DE ALMACENAMIENTO ==="
Write-Output "Disco C: Total            : $([math]::Round($disk.Size/1GB,1)) GB"
Write-Output "Disco C: Espacio Libre    : $([math]::Round($disk.FreeSpace/1GB,1)) GB ($([math]::Round(($disk.FreeSpace/$disk.Size)*100,1)) % libre)"
Write-Output ""
Write-Output "=== ESTADO DE VIRTUSTPVNET ==="
if ($v) {
    Write-Output "PID                       : $($v.Id)"
    Write-Output "Estado de la Pantalla     : $(if ($v.Responding) { 'RESPONDIENDO (OK)' } else { 'CONGELADO (NO RESPONDE)' })"
    Write-Output "Memoria RAM Ocupada       : $([math]::Round($v.WorkingSet64/1MB,1)) MB"
    Write-Output "Tiempo CPU Acumulado      : $([math]::Round($v.CPU,1)) segundos"
} else {
    Write-Output "VirtusTPVNet NO esta en ejecucion."
}
Write-Output ""
Write-Output "=== CONECTIVIDAD CON TPV 1 (MASTER) ==="
Write-Output "Puerto 3306 (MySQL)       : $(if ($mysqlTest.TcpTestSucceeded) { 'OK (Conectado)' } else { 'ERROR / Desconectado' })"
Write-Output "Puerto 8777 (SDES Pista)  : $(if ($sdesTest.TcpTestSucceeded) { 'OK (Conectado)' } else { 'ERROR / Desconectado' })"
Write-Output ""
Write-Output "=== TOP PROCESOS POR CONSUMO DE RAM ==="
$topRam | Format-Table -AutoSize | Out-String | Write-Output
Write-Output "=== TOP PROCESOS POR TIEMPO DE CPU ==="
$topCpu | Format-Table -AutoSize | Out-String | Write-Output

