Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$p = Get-Process WeChat -ErrorAction Stop | Select-Object -First 1
$root = [System.Windows.Automation.AutomationElement]::RootElement
$pidCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $p.Id)
$win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $pidCond)
if (-not $win) { "NO WINDOW"; exit 1 }
"window: " + $win.Current.Name + " class=" + $win.Current.ClassName

$all = $win.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
"descendants: " + $all.Count

$rows = foreach ($e in $all) {
    $n = $e.Current.Name
    if ($n -and $n.Length -gt 0 -and $n.Length -lt 60) {
        [pscustomobject]@{ Name = $n; Type = $e.Current.ControlType.ProgrammaticName; Class = $e.Current.ClassName }
    }
}
"named elements: " + ($rows | Measure-Object).Count
$rows | Select-Object -First 60 | Format-Table -AutoSize
