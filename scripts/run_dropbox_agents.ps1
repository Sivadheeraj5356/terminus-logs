# Private Harbor runs on extracted Dropbox tasks. No Snorkel/stb/Portkey.
# Usage (PowerShell), set a key in THIS shell, do not paste it into chat:
#   $env:OPENAI_API_KEY = "sk-..."              # then openai/gpt-4o
#   $env:ANTHROPIC_API_KEY = "sk-ant-..."       # then anthropic/claude-sonnet-4-5
#   .\scripts\run_dropbox_agents.ps1
# After jobs finish:
#   python scripts\update_catalog_from_jobs.py

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tasks = Join-Path $root "dropbox-tasks\latest"
$jobs = Join-Path $root "jobs"

Remove-Item Env:OPENAI_BASE_URL -ErrorAction SilentlyContinue

$anthropic = $env:ANTHROPIC_API_KEY
$openai = $env:OPENAI_API_KEY

if ($anthropic -and $anthropic.StartsWith("sk-ant-")) {
    $model = "anthropic/claude-sonnet-4-5"
} elseif ($openai -and ($openai.StartsWith("sk-") -or $openai.StartsWith("sk-proj-"))) {
    $model = "openai/gpt-4o"
} else {
    throw @"
No private model key in this shell.

Set one of:
  `$env:OPENAI_API_KEY = '<your OpenAI key>'
  `$env:ANTHROPIC_API_KEY = '<your Anthropic key>'

The user-level ANTHROPIC_API_KEY on this machine is an OpenAI sk-proj value, not an Anthropic key, and OpenAI already rejected it. Do not paste keys into chat.
"@
}

Write-Host "Private Harbor: terminus-2 + $model  (openai_len=$($openai.Length) anthropic_len=$($anthropic.Length))"

harbor run `
    -p $tasks `
    -a terminus-2 `
    -m $model `
    -k 1 `
    -n 2 `
    -o $jobs `
    --job-name dropbox-terminus-agents `
    -y
