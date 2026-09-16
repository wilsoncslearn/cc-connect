[CmdletBinding()]
param(
    [ValidateSet('Prepare', 'Build', 'Check', 'Start', 'Install')]
    [string]$Action = 'Prepare',
    [string]$RuntimeDir = (Join-Path $HOME '.cc-connect\personal-deploy'),
    [string]$GoCommand = 'go'
)
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$runtime = [IO.Path]::GetFullPath($RuntimeDir)
# Keep credentials and generated files outside the checkout.
if ($runtime.TrimEnd('\') -ieq $repo.TrimEnd('\') -or
    $runtime.StartsWith($repo.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'RuntimeDir must be outside the repository.'
}
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$local = Join-Path $runtime 'machine.local.json'
$config = Join-Path $runtime 'config.toml'
$binary = Join-Path $runtime 'cc-connect.exe'
$running = Get-Process -Name 'cc-connect' -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -ieq $binary }
if ($running) { throw 'This deployment is running. Stop it before updating its files.' }
if (-not (Test-Path -LiteralPath $local)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'machine.example.json') -Destination $local
}
$template = Join-Path $PSScriptRoot 'config.example.toml'
if (Test-Path -LiteralPath $config) {
    if ((Get-FileHash -LiteralPath $config).Hash -ne (Get-FileHash -LiteralPath $template).Hash) {
        Copy-Item -LiteralPath $config -Destination ($config + '.' + [guid]::NewGuid().ToString('N') + '.bak')
    }
}
Copy-Item -LiteralPath $template -Destination $config
if ($Action -eq 'Prepare') {
    Write-Output "Prepared templates; edit $local before Check/Start/Install. No service changed."
    return
}
if ($Action -eq 'Build') {
    $oldCGO = $env:CGO_ENABLED
    Push-Location -LiteralPath $repo
    try {
        $env:CGO_ENABLED = '0'
        & $GoCommand build -tags 'no_web,goolm' -o $binary ./cmd/cc-connect
        if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
    } finally {
        Pop-Location
        $env:CGO_ENABLED = $oldCGO
    }
    Write-Output "Built $binary. No service started."
    return
}
$settings = Get-Content -LiteralPath $local -Raw -Encoding UTF8 | ConvertFrom-Json
$optional = @('CC_TELEGRAM_PROXY', 'CC_WEIXIN_PROXY')
$keys = [regex]::Matches((Get-Content -LiteralPath $template -Raw), '\$\{(CC_[A-Z_]+)\}') |
    ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
foreach ($key in $keys) {
    $value = $settings.$key
    if ($value -isnot [string] -or ($key -notin $optional -and [string]::IsNullOrWhiteSpace($value))) {
        throw "Missing or invalid local setting: $key"
    }
}
foreach ($key in @('CC_TELEGRAM_USER_ID', 'CC_WEIXIN_USER_ID')) {
    if ($settings.$key.Contains('*')) { throw "Wildcard access is not allowed: $key" }
}
if ($settings.CC_TELEGRAM_USER_ID -notmatch '^\d+(\s*,\s*\d+)*$') {
    throw 'CC_TELEGRAM_USER_ID must contain numeric user IDs, separated by commas.'
}
if (-not [IO.Path]::IsPathRooted($settings.CC_WORK_DIR) -or
    -not (Test-Path -LiteralPath $settings.CC_WORK_DIR -PathType Container)) { throw 'Invalid absolute CC_WORK_DIR.' }
if (-not [IO.Path]::IsPathRooted($settings.CC_CODEX_CMD) -or
    -not (Test-Path -LiteralPath $settings.CC_CODEX_CMD -PathType Leaf) -or
    [IO.Path]::GetExtension($settings.CC_CODEX_CMD) -ine '.exe') {
    throw 'CC_CODEX_CMD must point to the native Codex .exe, not an npm .cmd wrapper.'
}
foreach ($key in $keys) { [Environment]::SetEnvironmentVariable($key, $settings.$key, 'Process') }
Write-Warning 'YOLO is enabled: no Codex sandbox or approval prompts.'
if ($Action -eq 'Check') { Write-Output 'Local settings valid. No bot connection or service change.'; return }
if (-not (Test-Path -LiteralPath $binary -PathType Leaf)) { throw 'Run Build first.' }
if ($Action -eq 'Install') {
    # Native installer captures referenced environment for the local scheduled task.
    # No --force: do not replace an existing service without an explicit handoff.
    & $binary daemon install --config $config
} else {
    & $binary --config $config
}
if ($LASTEXITCODE -ne 0) { throw "$Action failed (exit $LASTEXITCODE)." }
