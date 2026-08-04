$port = New-Object System.IO.Ports.SerialPort "COM4", 115200
$port.Open()
Start-Sleep -Milliseconds 500
$port.WriteLine("PING")
Start-Sleep -Milliseconds 800
$resp = $port.ReadExisting()
$port.Close()
Write-Host "MCU response: [$resp]"
