$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$healthUrl = 'http://127.0.0.1:8000/api/health'
$siteUrl = 'http://localhost:8000/'

function Test-HarvestLink {
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 1
        return ($health.ok -eq $true -and $health.database -eq 'sqlite')
    } catch {
        return $false
    }
}

if (-not (Test-HarvestLink)) {
    $python = $null
    $pythonArgs = @('-u', 'server.py')
    $pyLauncher = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $python = $pyLauncher.Source
        $pythonArgs = @('-3', '-u', 'server.py')
    } else {
        $pythonCommand = Get-Command 'python.exe' -ErrorAction SilentlyContinue
        if ($pythonCommand) { $python = $pythonCommand.Source }
    }
    if (-not $python) {
        $bundled = 'C:\Users\B70826\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
        if (Test-Path -LiteralPath $bundled) { $python = $bundled }
    }
    if (-not $python) {
        throw 'Python was not found. Install Python 3.10 or newer, then run this launcher again.'
    }
    Start-Process -FilePath $python -ArgumentList $pythonArgs -WorkingDirectory $root -WindowStyle Hidden | Out-Null
    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 500
        if (Test-HarvestLink) { $ready = $true; break }
    }
    if (-not $ready) {
        throw 'HarvestLink did not start on port 8000. Check whether another app is using that port, then try again.'
    }
}
Start-Process $siteUrl
