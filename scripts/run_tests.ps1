#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run the MiniMax HA integration test suite on Windows.

.DESCRIPTION
    pytest-homeassistant-custom-component tries to import fcntl/resource/pwd/grp
    at collection time, which fails on Windows. This script works around that by:
      1. Installing a tiny user-site stub (idempotent) that injects fake fcntl /
         resource / pwd / grp modules into sys.modules.
      2. Disabling pytest's plugin auto-loading and explicitly loading only the
         plugins we need (asyncio, pytest_cov, pytest_timeout, pytest_aiohttp).
      3. Running pytest with --confcutdir=. so tests/conftest.py is used.

.PARAMETER Path
    Optional pytest path / test id to run. Defaults to "tests/".

.PARAMETER NoCoverage
    Skip the coverage plugin (faster local runs).

.PARAMETER VerboseOutput
    Pass -v to pytest.

.EXAMPLE
    .\scripts\run_tests.ps1
    .\scripts\run_tests.ps1 -Path "tests/test_memory.py"
    .\scripts\run_tests.ps1 -Path "tests/test_ai_task.py::TestSchemaHelpers" -VerboseOutput
    .\scripts\run_tests.ps1 -NoCoverage
#>
[CmdletBinding()]
param(
    [string]$Path = "tests/",
    [switch]$NoCoverage,
    [switch]$VerboseOutput
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $repoRoot
try {
    $userSite = python -c "import site; print(site.getusersitepackages())"
    if (-not (Test-Path $userSite)) {
        New-Item -ItemType Directory -Path $userSite -Force | Out-Null
    }

    $stubPath = Join-Path $userSite "sitecustomize.py"
    $stub = @'
"""Windows stub: provide dummy fcntl/resource/pwd/grp modules for tests."""
import sys
import types


def _install(name):
    if name in sys.modules:
        return
    mod = types.ModuleType(name)
    if name == "fcntl":
        mod.LOCK_EX = 2
        mod.LOCK_SH = 1
        mod.LOCK_NB = 4
        mod.LOCK_UN = 8
        mod.flock = lambda *a, **k: 0
        mod.ioctl = lambda *a, **k: 0
    elif name == "resource":
        mod.RLIMIT_CPU = 0
        mod.RLIMIT_NOFILE = 7
        mod.getrlimit = lambda *a, **k: (0, 0)
        mod.setrlimit = lambda *a, **k: None
    elif name == "pwd":
        mod.getpwnam = lambda *a, **k: types.SimpleNamespace(pw_uid=0)
        mod.getpwuid = lambda *a, **k: types.SimpleNamespace(pw_name="root")
    elif name == "grp":
        mod.getgrnam = lambda *a, **k: types.SimpleNamespace(gr_gid=0)
        mod.getgrgid = lambda *a, **k: types.SimpleNamespace(gr_name="root")
    sys.modules[name] = mod


for _name in ("fcntl", "resource", "pwd", "grp"):
    _install(_name)
'@

    Set-Content -LiteralPath $stubPath -Value $stub -Encoding UTF8
    Write-Host "Wrote sitecustomize.py stub to $stubPath" -ForegroundColor DarkGray

    $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"

    $plugins = @("asyncio", "pytest_cov", "pytest_timeout", "pytest_aiohttp")

    $commonArgs = @(
        "--no-header",
        "--tb=line",
        "--confcutdir=.",
        "--asyncio-mode=auto"
    )
    foreach ($plugin in $plugins) {
        $commonArgs += @("-p", $plugin)
    }

    if ($VerboseOutput) { $commonArgs += "-v" }
    if ($NoCoverage) { $commonArgs += "--no-cov" }

    Write-Host "Running: pytest $Path $($commonArgs -join ' ')" -ForegroundColor Cyan
    & python -m pytest $Path @commonArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
