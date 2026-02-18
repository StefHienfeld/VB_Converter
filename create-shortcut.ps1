$WshShell = New-Object -ComObject WScript.Shell
$Desktop = [Environment]::GetFolderPath('Desktop')
$Shortcut = $WshShell.CreateShortcut("$Desktop\VB Converter.lnk")
$Shortcut.TargetPath = "C:\Users\Stef\Desktop\Vb agent\start.bat"
$Shortcut.WorkingDirectory = "C:\Users\Stef\Desktop\Vb agent"
$Shortcut.Save()
Write-Host "Snelkoppeling aangemaakt op Desktop: VB Converter.lnk"
