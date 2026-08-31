# Private Harbor batch for docs/lab_batch_0N.jsonl.
# Do NOT use run_agents.ps1 (that still defaults sonnet/gpt-4o over all of tasks/latest).
#
# Harbor 0.22: n_trials = n_attempts x n_tasks x n_agents.
#   -k / --n-attempts  = independent trials (cartesian product), NOT intra-trial retries
#   -n / --n-concurrent = parallelism (keep 1, at most 2)
#   --retry             = infra retries (leave off / 0)
# Going-forward: 5 independent trials x two cheap arms (Haiku + gpt-4o-mini / Sonnet fallback)
#
# Usage (PowerShell), keys in THIS shell, never paste into chat:
#   $env:ANTHROPIC_API_KEY = "sk-ant-..."
#   $env:OPENAI_API_KEY    = "sk-..."
#   .\scripts\run_lab_batch.ps1 -Phase probe -Batch 1
#   .\scripts\run_lab_batch.ps1 -Phase oracle -Batch 1
#   .\scripts\run_lab_batch.ps1 -Phase smoke -Batch 1
#   .\scripts\run_lab_batch.ps1 -Phase measure -Batch 1 -YesMeasure
#   .\scripts\run_lab_batch.ps1 -Phase classify
#
# Linux equivalent: python3 scripts/run_lab_batch.py --phase probe --batch 1

[CmdletBinding()]
param(
    [ValidateSet("probe", "oracle", "smoke", "measure", "empty", "classify", "all")]
    [string]$Phase = "probe",
    [int]$Batch = 1,
    [string]$BatchJsonl = "",
    [string]$HaikuModel = "anthropic/claude-haiku-4-5",
    [string]$SecondModel = "openai/gpt-4o-mini",
    [string]$SecondFallback = "anthropic/claude-sonnet-4-5",
    [string]$SmokeSlug = "",
    [int]$Trials = 5,
    [int]$Concurrent = 1,
    [int]$StopAfterTasks = 0,
    [switch]$YesMeasure
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$batchTag = "{0:d2}" -f $Batch
if (-not $BatchJsonl) {
    $BatchJsonl = Join-Path $root "docs\lab_batch_$batchTag.jsonl"
}
$jobs = Join-Path $root "jobs"
$tasksRoot = Join-Path $root "tasks\latest"
New-Item -ItemType Directory -Force -Path $jobs | Out-Null

function Get-BatchRows {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        throw "Missing $Path — run python scripts/select_lab_batch.py"
    }
    $rows = @()
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if ($line) {
            $rows += ($line | ConvertFrom-Json)
        }
    }
    if ($rows.Count -ne 10) {
        throw "$Path has $($rows.Count) rows, expected 10"
    }
    return $rows
}

function Assert-Keys {
    $anthropic = $env:ANTHROPIC_API_KEY
    $openai = $env:OPENAI_API_KEY
    if (-not $anthropic) { throw "ANTHROPIC_API_KEY is not set in this shell." }
    if ($anthropic.StartsWith("sk-proj-")) {
        throw "ANTHROPIC_API_KEY is an OpenAI sk-proj- value. Need sk-ant-... in the Harbor shell."
    }
    if (-not $anthropic.StartsWith("sk-ant-")) {
        throw "ANTHROPIC_API_KEY must start with sk-ant-."
    }
    if (-not $openai) { throw "OPENAI_API_KEY is not set in this shell." }
    if (-not ($openai.StartsWith("sk-") -or $openai.StartsWith("sk-proj-"))) {
        throw "OPENAI_API_KEY does not look like an OpenAI key."
    }
    Write-Host "Keys: anthropic_len=$($anthropic.Length) openai_len=$($openai.Length) (prefixes not printed)"
}

function Confirm-HarborK {
    $harbor = Get-Command harbor -ErrorAction SilentlyContinue
    if (-not $harbor) {
        throw "harbor is not on PATH. Install Harbor 0.22 on the evaluation host."
    }
    Write-Host "harbor: $($harbor.Source)"
    $help = & harbor run --help 2>&1 | Out-String
    $lines = $help -split "`r?`n" | Where-Object {
        $_ -match "n-attempts|n_attempts|-k |n-trials|n_trials|attempts per"
    }
    Write-Host "Harbor n_trials vs -k (from harbor run --help):"
    if ($lines) {
        $lines | ForEach-Object { Write-Host "  $_" }
    } else {
        Write-Host "  (no -k / n-attempts / n-trials lines parsed; still using -k as n_attempts)"
    }
    Write-Host "Interpretation: n_trials = n_attempts x tasks x agents. -k $Trials => $Trials independent trials. -n $Concurrent concurrency. --retry left off."
}

function Invoke-Harbor {
    param(
        [string]$Package,
        [string]$Agent,
        [string]$Model,
        [int]$K,
        [string]$JobName
    )
    $pkg = Join-Path $tasksRoot $Package
    if (-not (Test-Path $pkg)) {
        throw "Package missing: $pkg"
    }
    Write-Host ">> harbor run -p $Package -a $Agent $(if ($Model) { "-m $Model" }) -k $K -n $Concurrent --job-name $JobName"
    $args = @(
        "run",
        "-p", $pkg,
        "-a", $Agent,
        "-k", "$K",
        "-n", "$Concurrent",
        "-o", $jobs,
        "--job-name", $JobName,
        "-y"
    )
    if ($Model) {
        $args = @(
            "run",
            "-p", $pkg,
            "-a", $Agent,
            "-m", $Model,
            "-k", "$K",
            "-n", "$Concurrent",
            "-o", $jobs,
            "--job-name", $JobName,
            "-y"
        )
    }
    & harbor @args
    if ($LASTEXITCODE -ne 0) {
        throw "harbor failed ($LASTEXITCODE) for $JobName"
    }
}

function Invoke-Probe {
    Assert-Keys
    Confirm-HarborK
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) { throw "docker is not on PATH." }
    & docker info | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker info failed." }
    Write-Host "Probe ok. Smoke slug will be first frozen row unless -SmokeSlug is set. Haiku=$HaikuModel Second=$SecondModel"
    & python (Join-Path $root "scripts\probe_lab_runtime.py") --haiku-model $HaikuModel --second-model $SecondModel
}

function Invoke-Oracle {
    Assert-Keys
    $rows = Get-BatchRows $BatchJsonl
    $i = 0
    foreach ($row in $rows) {
        $i++
        Invoke-Harbor -Package $row.slug -Agent "oracle" -Model "" -K 1 -JobName "lab$batchTag-oracle-$($row.slug.Substring(0, [Math]::Min(40, $row.slug.Length)))"
        if ($StopAfterTasks -gt 0 -and $i -ge $StopAfterTasks) {
            Write-Host "StopAfterTasks=$StopAfterTasks — leaving remaining oracle runs."
            break
        }
    }
}

function Invoke-Smoke {
    Assert-Keys
    Confirm-HarborK
    $rows = Get-BatchRows $BatchJsonl
    if (-not $SmokeSlug) { $SmokeSlug = $rows[0].slug }
    try {
        Invoke-Harbor -Package $SmokeSlug -Agent "terminus-2" -Model $HaikuModel -K 1 -JobName "lab$batchTag-smoke-haiku"
    } catch {
        throw "Haiku smoke failed. Confirm LiteLLM slug (tried $HaikuModel). Do not start k=5 measure. $_"
    }
    try {
        Invoke-Harbor -Package $SmokeSlug -Agent "terminus-2" -Model $SecondModel -K 1 -JobName "lab$batchTag-smoke-second"
    } catch {
        Write-Host "Second arm failed on $SecondModel — retrying $SecondFallback"
        Invoke-Harbor -Package $SmokeSlug -Agent "terminus-2" -Model $SecondFallback -K 1 -JobName "lab$batchTag-smoke-second-fallback"
        $script:SecondModel = $SecondFallback
    }
    Write-Host "Smoke ok. Measure with -Phase measure -YesMeasure (cheap k=5 x two arms)."
}

function Invoke-Measure {
    Assert-Keys
    if (-not $YesMeasure) {
        throw "Refusing cheap k=5 measure without -YesMeasure. Run -Phase smoke first."
    }
    $rows = Get-BatchRows $BatchJsonl
    $i = 0
    foreach ($row in $rows) {
        $i++
        $short = $row.slug.Substring(0, [Math]::Min(36, $row.slug.Length))
        Invoke-Harbor -Package $row.slug -Agent "terminus-2" -Model $HaikuModel -K $Trials -JobName "lab$batchTag-haiku-$short"
        Invoke-Harbor -Package $row.slug -Agent "terminus-2" -Model $SecondModel -K $Trials -JobName "lab$batchTag-second-$short"
        if ($StopAfterTasks -gt 0 -and $i -ge $StopAfterTasks) {
            Write-Host "StopAfterTasks=$StopAfterTasks — not auto-starting remaining tasks or the next batch."
            break
        }
    }
}

function Invoke-Empty {
    $rows = Get-BatchRows $BatchJsonl
    foreach ($row in $rows) {
        $short = $row.slug.Substring(0, [Math]::Min(36, $row.slug.Length))
        Invoke-Harbor -Package $row.slug -Agent "nop" -Model "" -K 1 -JobName "lab$batchTag-nop-$short"
    }
}

function Invoke-Classify {
    & python (Join-Path $root "scripts\ingest_lab_jobs.py")
    & python (Join-Path $root "scripts\update_catalog_from_jobs.py")
}

switch ($Phase) {
    "probe" { Invoke-Probe }
    "oracle" { Invoke-Oracle }
    "smoke" { Invoke-Smoke }
    "measure" { Invoke-Measure }
    "empty" { Invoke-Empty }
    "classify" { Invoke-Classify }
    "all" {
        Invoke-Probe
        Invoke-Oracle
        Invoke-Smoke
        if ($YesMeasure) {
            Invoke-Measure
            Invoke-Empty
        } else {
            Write-Host "Smoke finished. Re-run with -Phase measure -YesMeasure to spend cheap k=5 jobs."
        }
        Invoke-Classify
    }
}
