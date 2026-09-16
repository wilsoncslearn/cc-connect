# Native UI Automation only: no private IPC, process termination, or DB writes.
# ponytail: pinned/hidden/ambiguous tasks fail closed; add ID-based API when exposed.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$attempted = $false
try {
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$inputData = [Console]::In.ReadToEnd() | ConvertFrom-Json
if ($inputData.action -notin @('archive', 'restore')) { throw 'Invalid action' }
$title = [string]$inputData.title
if ([string]::IsNullOrWhiteSpace($title)) { throw 'Missing task title' }
$apps = @(Get-Process ChatGPT -ErrorAction SilentlyContinue | Where-Object {
    $_.MainWindowHandle -ne 0 -and $_.Path -like '*\WindowsApps\OpenAI.Codex_*\app\ChatGPT.exe'
})
if ($apps.Count -ne 1) { throw 'Cannot identify one Codex desktop window' }
$app = $apps[0]
if ($inputData.action -eq 'archive') {
    $owner = Get-CimInstance Win32_Process -Filter ('ProcessId = {0}' -f [int]$inputData.owner_pid)
    if ($null -eq $owner -or $owner.Name -ne 'codex.exe' -or $owner.ParentProcessId -ne $app.Id) {
        throw 'Writer is not owned by this desktop window'
    }
    $writer = Get-Process -Id ([int]$inputData.owner_pid)
    if ($writer.StartTime.ToUniversalTime().ToFileTimeUtc() -ne [long]$inputData.owner_start) {
        throw 'Writer identity changed; no action requested'
    }
}
$root = [System.Windows.Automation.AutomationElement]::FromHandle($app.MainWindowHandle)
$scope = [System.Windows.Automation.TreeScope]::Descendants
$nameProperty = [System.Windows.Automation.AutomationElement]::NameProperty
$typeProperty = [System.Windows.Automation.AutomationElement]::ControlTypeProperty
function Find-Elements($container, [string]$name, $type) {
    $condition = [System.Windows.Automation.AndCondition]::new(
        [System.Windows.Automation.PropertyCondition]::new($nameProperty, $name),
        [System.Windows.Automation.PropertyCondition]::new($typeProperty, $type))
    return ,$container.FindAll($scope, $condition)
}
function Get-One($container, [string]$name, $type, [int]$waitMs = 0) {
    $deadline = [DateTime]::UtcNow.AddMilliseconds($waitMs)
    do {
        $found = Find-Elements $container $name $type
        if ($found.Count -eq 1) { return $found.Item(0) }
        if ($found.Count -gt 1) { throw "Ambiguous UI control: $name" }
        if ([DateTime]::UtcNow -ge $deadline) { throw "UI control unavailable: $name" }
        Start-Sleep -Milliseconds 100
    } while ($true)
}
function Invoke-Control($element) {
    if (-not $element.Current.IsEnabled) { throw 'UI control disabled' }
    ([System.Windows.Automation.InvokePattern]$element.GetCurrentPattern(
        [System.Windows.Automation.InvokePattern]::Pattern)).Invoke()
}
function Return-ToApp {
    $back = Find-Elements $root '返回应用' ([System.Windows.Automation.ControlType]::Hyperlink)
    if ($back.Count -eq 1) { Invoke-Control $back.Item(0) }
    elseif ($back.Count -gt 1) { throw 'Ambiguous settings view' }
}
if ($inputData.action -eq 'archive') {
    Return-ToApp
    $list = Get-One $root ([string]$inputData.project + '中的已安排任务') ([System.Windows.Automation.ControlType]::List) 3000
    $item = Get-One $list $title ([System.Windows.Automation.ControlType]::ListItem)
    $states = $item.FindAll($scope, [System.Windows.Automation.PropertyCondition]::new(
        $typeProperty, [System.Windows.Automation.ControlType]::StatusBar))
    if ($states.Count -ne 0) { throw 'Task is busy or requires attention; not archived' }
    $button = Get-One $item '归档聊天' ([System.Windows.Automation.ControlType]::Button)
    $attempted = $true
    Invoke-Control $button
} else {
    $archived = Find-Elements $root '已归档的聊天' ([System.Windows.Automation.ControlType]::Button)
    if ($archived.Count -eq 0) {
        $profile = Get-One $root '打开个人资料菜单' ([System.Windows.Automation.ControlType]::Button) 3000
        ([System.Windows.Automation.ExpandCollapsePattern]$profile.GetCurrentPattern(
            [System.Windows.Automation.ExpandCollapsePattern]::Pattern)).Expand()
        Invoke-Control (Get-One $root '设置 Ctrl+,' ([System.Windows.Automation.ControlType]::MenuItem) 3000)
    }
    # Re-enter the view so an earlier settings visit cannot leave a stale list.
    Invoke-Control (Get-One $root '常规' ([System.Windows.Automation.ControlType]::Button) 10000)
    Invoke-Control (Get-One $root '已归档的聊天' ([System.Windows.Automation.ControlType]::Button) 10000)
    $search = Get-One $root '搜索已归档聊天' ([System.Windows.Automation.ControlType]::Edit) 10000
    ([System.Windows.Automation.ValuePattern]$search.GetCurrentPattern(
        [System.Windows.Automation.ValuePattern]::Pattern)).SetValue($title)
    $label = Get-One $root $title ([System.Windows.Automation.ControlType]::Text) 10000
    # RawView preserves the row; ControlView flattens all archived rows together.
    $row = [System.Windows.Automation.TreeWalker]::RawViewWalker.GetParent($label)
    $restore = Get-One $row '取消归档' ([System.Windows.Automation.ControlType]::Button)
    $attempted = $true
    Invoke-Control $restore
    # Stay away from the restored task, otherwise viewing it can reclaim its lock.
    Return-ToApp
}
@{ action = $inputData.action; desktop_pid = $app.Id } | ConvertTo-Json -Compress

} catch {
    @{ error = $_.Exception.Message; attempted = $attempted } | ConvertTo-Json -Compress
    exit 1
}
