$binPath = "C:\Users\Stef\.local\bin"
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$binPath*") {
    $newPath = $currentPath.TrimEnd(";") + ";" + $binPath
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "Added $binPath to user PATH. Restart your terminal for it to take effect."
} else {
    Write-Host "$binPath is already in user PATH."
}
