$python = "c:\Coding\molebuild-scraper\.venv\Scripts\python.exe"
$script = "c:\Coding\molebuild-scraper\auto_scraper2.py"
$arguments = @($script, "--python", $python, "--interval", "300")

$running = @(
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like "*auto_scraper2.py*" } |
        Sort-Object ProcessId
)

if ($running.Count -gt 1) {
    $running | Select-Object -Skip 1 | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    return
}

if ($running.Count -eq 1) {
    return
}

Start-Process -FilePath $python -ArgumentList $arguments -WindowStyle Hidden -WorkingDirectory "c:\Coding\molebuild-scraper"
