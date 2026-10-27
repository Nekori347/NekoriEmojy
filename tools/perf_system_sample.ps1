param([Parameter(Mandatory=$true)][string]$Output, [int]$Samples=30)
# Bounded read-only PDH sampling. No ETW session, memory pressure or app input.
$paths = @(
 '\Memory\Available MBytes', '\Memory\Committed Bytes', '\Memory\Commit Limit',
 '\Memory\Page Reads/sec', '\Memory\Pages Input/sec', '\Memory\Pages/sec',
 '\Processor(_Total)\% Processor Time', '\PhysicalDisk(_Total)\Avg. Disk sec/Read',
 '\PhysicalDisk(_Total)\Disk Read Bytes/sec',
 '\Process(NekoriEmojy*)\Working Set', '\Process(NekoriEmojy*)\Private Bytes',
 '\Process(NekoriEmojy*)\Page Faults/sec', '\Process(NekoriEmojy*)\% Processor Time',
 '\Process(Eagle*)\% Processor Time', '\Process(Eagle*)\Page Faults/sec')
$result = Get-Counter -Counter $paths -SampleInterval 1 -MaxSamples $Samples |
 ForEach-Object {
  $time = $_.Timestamp.ToUniversalTime().ToString('o')
  foreach ($item in $_.CounterSamples) {
   # Remove machine name; only counter identity, time and value persist.
   [pscustomobject]@{utc=$time; counter=($item.Path -replace '^\\\\[^\\]+',''); value=$item.CookedValue; status=$item.Status}
  }
 }
$result | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $Output -Encoding utf8
