$uninstallKey = 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'
Get-ChildItem -Path $uninstallKey | ForEach-Object {
    $name = $_.PSChildName
    if ($name -like 'RMS_*') {
        Write-Host "Deleting uninstall key: $name"
        Remove-Item -Path ('{0}\{1}' -f $uninstallKey, $name) -Recurse -Force -ErrorAction SilentlyContinue
        $folder = Join-Path 'C:\ProgramData' $name
        if (Test-Path $folder) { 
            Remove-Item $folder -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
