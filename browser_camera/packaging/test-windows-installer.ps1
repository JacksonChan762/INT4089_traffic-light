[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $Installer
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Setup {
    param(
        [string] $Executable,
        [string[]] $Arguments,
        [string] $Log
    )
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -PassThru -Wait
    if ($process.ExitCode -ne 0) {
        if (Test-Path -LiteralPath $Log) {
            Get-Content -LiteralPath $Log -Tail 25 | Write-Host
        }
        throw "$Executable exited with code $($process.ExitCode)."
    }
}

$installerPath = (Resolve-Path -LiteralPath $Installer).ProviderPath
$shortcutPath = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Traffic Light Camera.lnk'
if (Test-Path -LiteralPath $shortcutPath) {
    throw 'Run this smoke test from a Windows account without Traffic Light Camera installed.'
}

$work = Join-Path ([IO.Path]::GetTempPath()) ('Traffic Light Camera Test ' + [Guid]::NewGuid().ToString('N'))
$installDir = Join-Path $work 'Installed Traffic Light Camera'
$launcher = Join-Path $installDir 'Start.cmd'
$python = Join-Path $installDir 'python\python.exe'
$uninstaller = Join-Path $installDir 'unins000.exe'
$setupLog = Join-Path $work 'setup.log'
$uninstallLog = Join-Path $work 'uninstall.log'
$serverOutput = Join-Path $work 'server.out'
$serverError = Join-Path $work 'server.err'
$server = $null

New-Item -Path $work -ItemType Directory | Out-Null
try {
    Invoke-Setup -Executable $installerPath -Arguments @(
        '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-',
        ('/DIR="{0}"' -f $installDir), ('/LOG="{0}"' -f $setupLog)
    ) -Log $setupLog

    foreach ($installedFile in @($launcher, $python, $uninstaller, $shortcutPath)) {
        if (-not (Test-Path -LiteralPath $installedFile -PathType Leaf)) {
            throw "Installer did not create $installedFile."
        }
    }
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    if ($shortcut.TargetPath -ne $launcher -or $shortcut.WorkingDirectory -ne $installDir) {
        throw "Unexpected Start menu shortcut target or working directory at $shortcutPath."
    }

    $help = & $launcher --help
    if ($LASTEXITCODE -ne 0 -or ($help -join "`n") -notmatch '--open-browser') {
        throw 'The installed Start.cmd --help did not return the camera host options.'
    }

    $server = Start-Process -FilePath $python -WorkingDirectory $installDir -ArgumentList @(
        '-E', '-s', '-B', 'launch.py', '--bind', '127.0.0.1', '--port', '0',
        '--esp', 'http://127.0.0.1'
    ) -RedirectStandardOutput $serverOutput -RedirectStandardError $serverError -PassThru -WindowStyle Hidden
    $baseUrl = $null
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($server.HasExited) {
            Get-Content -LiteralPath $serverError | Write-Host
            throw "The installed camera host exited with code $($server.ExitCode)."
        }
        if ((Get-Content -Raw -LiteralPath $serverOutput) -match 'Open (http://127\.0\.0\.1:\d+) in your browser') {
            $baseUrl = $Matches[1]
            break
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $baseUrl) {
        throw 'The installed camera host did not announce its loopback URL.'
    }

    $dashboard = Invoke-WebRequest -UseBasicParsing -Uri "$baseUrl/" -TimeoutSec 5
    if ($dashboard.StatusCode -ne 200 -or $dashboard.Content -notmatch '<html lang="en"' -or
        $dashboard.Content -notmatch 'Camera counting' -or $dashboard.Content -notmatch 'Light timing log' -or
        $dashboard.Content -notmatch 'href="\./traffic-test"') {
        throw 'The installed camera host did not serve the dashboard with the light timing log.'
    }
    $simulator = Invoke-WebRequest -UseBasicParsing -Uri "$baseUrl/traffic-test" -TimeoutSec 5
    if ($simulator.StatusCode -ne 200 -or $simulator.Content -notmatch 'Traffic Light Test Lab') {
        throw 'The installed camera host did not serve the traffic simulator.'
    }
    Write-Host 'Installed shortcut, launcher help, light timing log and simulator verified.'
} finally {
    if ($null -ne $server -and -not $server.HasExited) {
        Stop-Process -InputObject $server -Force
        $server.WaitForExit()
    }
    try {
        if (Test-Path -LiteralPath $uninstaller -PathType Leaf) {
            Invoke-Setup -Executable $uninstaller -Arguments @(
                '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/LOG="{0}"' -f $uninstallLog)
            ) -Log $uninstallLog
            foreach ($installedFile in @($launcher, $python, $shortcutPath)) {
                if (Test-Path -LiteralPath $installedFile) {
                    throw "The uninstaller left $installedFile in place."
                }
            }
            Write-Host 'Silent uninstall removed the app and Start menu shortcut.'
        }
    } finally {
        Remove-Item -LiteralPath $work -Recurse -Force
    }
}
