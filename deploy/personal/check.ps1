$ErrorActionPreference = 'Stop'
$deploy = Join-Path $PSScriptRoot 'deploy.ps1'
$runtime = Join-Path ([IO.Path]::GetTempPath()) ("cc personal's & check " + [guid]::NewGuid().ToString('N'))
function Expect-Failure([scriptblock]$Run, [string]$Expected) {
    try { & $Run } catch {
        if ($_.Exception.Message -notlike "*$Expected*") { throw }
        return
    }
    throw "Expected failure: $Expected"
}
& $deploy -RuntimeDir $runtime -Action Prepare
$local = Join-Path $runtime 'machine.local.json'
$before = (Get-FileHash -LiteralPath $local).Hash
& $deploy -RuntimeDir $runtime -Action Prepare
if ((Get-FileHash -LiteralPath $local).Hash -ne $before) { throw 'Prepare overwrote local settings.' }
Expect-Failure { & $deploy -RuntimeDir $runtime -Action Check } 'Missing or invalid local setting'
$settings = Get-Content -LiteralPath $local -Raw | ConvertFrom-Json
$settings.CC_WORK_DIR = $runtime
$settings.CC_CODEX_CMD = (Get-Process -Id $PID).Path
$settings.CC_TELEGRAM_TOKEN = 'dummy-not-a-real-token'
$settings.CC_TELEGRAM_USER_ID = '12345'
$settings.CC_WEIXIN_TOKEN = 'dummy-not-a-real-token'
$settings.CC_WEIXIN_USER_ID = 'test-user@im.wechat'
$settings | ConvertTo-Json | Set-Content -LiteralPath $local -Encoding UTF8
& $deploy -RuntimeDir $runtime -Action Check
$config = Join-Path $runtime 'config.toml'
if ((Get-Content -LiteralPath $config -Raw) -notmatch 'cmd = \["\$\{CC_CODEX_CMD\}"\]') {
    throw 'Native exe path must use a TOML array to preserve spaces.'
}
Add-Content -LiteralPath $config -Value '# local change requiring backup'
$changedHash = (Get-FileHash -LiteralPath $config).Hash
& $deploy -RuntimeDir $runtime -Action Prepare
$backups = @(Get-ChildItem -LiteralPath $runtime -Filter 'config.toml.*.bak')
if ($backups.Count -ne 1 -or (Get-FileHash -LiteralPath $backups[0].FullName).Hash -ne $changedHash) {
    throw 'Generated config was overwritten without an intact backup.'
}
$settings.CC_TELEGRAM_USER_ID = '*'
$settings | ConvertTo-Json | Set-Content -LiteralPath $local -Encoding UTF8
Expect-Failure { & $deploy -RuntimeDir $runtime -Action Check } 'Wildcard access is not allowed'
Expect-Failure { & $deploy -RuntimeDir (Join-Path $PSScriptRoot 'forbidden-local') -Action Prepare } 'outside the repository'
Write-Output "PASS: offline deployment checks. Dummy test files: $runtime"
