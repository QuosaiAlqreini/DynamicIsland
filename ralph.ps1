<#
.SYNOPSIS
    Ralph Loop - Autonomous AI Agent Loop for Windows & PowerShell
.DESCRIPTION
    Runs an autonomous loop executing user stories from prd.json until all acceptance criteria
    are met and all stories have passes: true.
.PARAMETER MaxIterations
    Maximum number of iterations before stopping. Default: 10.
.PARAMETER Tool
    Tool runner to use. Options: 'agent' (Antigravity/local CLI), 'claude', or 'amp'. Default: 'agent'.
#>
[CmdletBinding()]
param(
    [int]$MaxIterations = 10,
    [ValidateSet('agent', 'claude', 'amp')]
    [string]$Tool = 'agent'
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PrdFile = Join-Path $ScriptDir "prd.json"
$ProgressFile = Join-Path $ScriptDir "progress.txt"
$ArchiveDir = Join-Path $ScriptDir "archive"
$LastBranchFile = Join-Path $ScriptDir ".last-branch"
$PromptFile = Join-Path $ScriptDir "prompt.md"

if (-not (Test-Path $PrdFile)) {
    Write-Warning "prd.json not found in $ScriptDir. Please initialize prd.json before running Ralph."
    exit 1
}

# Archive previous run if branch changed
if ((Test-Path $PrdFile) -and (Test-Path $LastBranchFile)) {
    try {
        $PrdContent = Get-Content $PrdFile -Raw | ConvertFrom-Json
        $CurrentBranch = $PrdContent.branchName
        $LastBranch = Get-Content $LastBranchFile -Raw
        $LastBranch = $LastBranch.Trim()

        if ($CurrentBranch -and $LastBranch -and ($CurrentBranch -ne $LastBranch)) {
            $DateStr = Get-Date -Format "yyyy-MM-dd"
            $CleanBranch = $LastBranch -replace "^ralph/", ""
            $ArchiveFolder = Join-Path $ArchiveDir "$DateStr-$CleanBranch"
            
            Write-Host "Archiving previous run ($LastBranch) to $ArchiveFolder..." -ForegroundColor Cyan
            New-Item -ItemType Directory -Path $ArchiveFolder -Force | Out-Null
            Copy-Item $PrdFile -Destination $ArchiveFolder -Force
            if (Test-Path $ProgressFile) {
                Copy-Item $ProgressFile -Destination $ArchiveFolder -Force
            }

            # Reset progress file
            "# Ralph Progress Log`nStarted: $(Get-Date)`n---`n" | Set-Content $ProgressFile -Encoding utf8
        }
    } catch {
        Write-Warning "Failed checking branch archive: $_"
    }
}

# Track current branch
try {
    $PrdContent = Get-Content $PrdFile -Raw | ConvertFrom-Json
    if ($PrdContent.branchName) {
        $PrdContent.branchName | Set-Content $LastBranchFile -Encoding utf8
    }
} catch {}

# Initialize progress file if missing
if (-not (Test-Path $ProgressFile)) {
    "# Ralph Progress Log`nStarted: $(Get-Date)`n---`n" | Set-Content $ProgressFile -Encoding utf8
}

Write-Host "==========================================================" -ForegroundColor Green
Write-Host " Starting Ralph Loop (Max iterations: $MaxIterations, Tool: $Tool)" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

for ($i = 1; $i -le $MaxIterations; $i++) {
    Write-Host "`n>>> Ralph Iteration $i of $MaxIterations ($Tool) <<<" -ForegroundColor Yellow

    # Check remaining stories
    $Prd = Get-Content $PrdFile -Raw | ConvertFrom-Json
    $Incomplete = @($Prd.userStories | Where-Object { -not $_.passes })

    if ($Incomplete.Count -eq 0) {
        Write-Host "`nAll stories in prd.json are marked as passes: true!" -ForegroundColor Green
        Write-Host "Ralph completed all tasks successfully at iteration $i!" -ForegroundColor Green
        exit 0
    }

    $NextStory = $Incomplete | Sort-Object priority | Select-Object -First 1
    Write-Host "Current Target: [$($NextStory.id)] $($NextStory.title) (Priority: $($NextStory.priority))" -ForegroundColor Cyan

    $Output = ""
    if ($Tool -eq 'claude') {
        $ClaudeConfig = Join-Path $ScriptDir "CLAUDE.md"
        $Output = Get-Content $ClaudeConfig -Raw | claude --dangerously-skip-permissions --print 2>&1 | Out-String
    } elseif ($Tool -eq 'amp') {
        $Output = Get-Content $PromptFile -Raw | amp --dangerously-allow-all 2>&1 | Out-String
    } else {
        Write-Host "Executing iterative step for [$($NextStory.id)]..." -ForegroundColor Cyan
        Write-Host "Hint: In Antigravity IDE, call the Ralph prompt or ask the agent to complete the next story in prd.json."
        break
    }

    Write-Host $Output

    if ($Output -match "<promise>COMPLETE</promise>") {
        Write-Host "`nRalph received completion signal: <promise>COMPLETE</promise>" -ForegroundColor Green
        Write-Host "All tasks completed!" -ForegroundColor Green
        exit 0
    }

    Start-Sleep -Seconds 2
}

Write-Host "`nReached maximum iterations ($MaxIterations) or interactive pause. Check $ProgressFile." -ForegroundColor Yellow
