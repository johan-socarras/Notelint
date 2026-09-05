<#
notelint installer - Windows.

    irm https://raw.githubusercontent.com/johan-socarras/notelint/main/install.ps1 | iex

Install somewhere other than ~\knowledge-base:

    & ([scriptblock]::Create((irm https://raw.githubusercontent.com/johan-socarras/notelint/main/install.ps1))) -Base C:\my-brain

It creates a knowledge base that is self-contained: the tools live inside it, so
if you later put the base in a synced folder, the tools travel with it.

Nothing is uploaded anywhere. Read this file before running it - that is the
whole point of piping to iex only after you have looked.
#>
[CmdletBinding()]
param(
    [string]$Base = (Join-Path $HOME 'knowledge-base'),
    [string]$Repo = 'johan-socarras/notelint',
    [string]$Branch = 'main',
    [string]$FirstProject = 'Example'
)

$ErrorActionPreference = 'Stop'

function Write-Step($t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }
function Write-Ok($t)   { Write-Host "  OK  " -ForegroundColor Green -NoNewline; Write-Host $t }
function Write-Warn($t) { Write-Host " WARN " -ForegroundColor Yellow -NoNewline; Write-Host $t }
function Write-Dim($t)  { Write-Host "      $t" -ForegroundColor DarkGray }
function Die($t)        { Write-Host " FAIL " -ForegroundColor Red -NoNewline; Write-Host $t; exit 1 }

Write-Host ""
Write-Host "  notelint - a linter for a knowledge base that does not rot" -ForegroundColor Cyan
Write-Host ""

# --------------------------------------------------------------- requirements
Write-Step "Checking requirements"

$py = $null
foreach ($c in @('python', 'python3', 'py')) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if (-not $cmd) { continue }
    try {
        $args = if ($c -eq 'py') { @('-3', '-c', 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)') }
                else { @('-c', 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)') }
        & $cmd.Source @args 2>$null
        if ($LASTEXITCODE -eq 0) {
            $py = if ($c -eq 'py') { "$($cmd.Source) -3" } else { $cmd.Source }
            break
        }
    } catch { }
}
if (-not $py) {
    Die "Python 3.8+ is required. Install it from python.org or: winget install Python.Python.3.12"
}
Write-Ok ((& ([scriptblock]::Create("$py --version")) 2>&1) -join ' ')

# ------------------------------------------------------------------- download
Write-Step "Downloading notelint"

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("notelint-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $tmp -Force | Out-Null

try {
    $zip = Join-Path $tmp 'src.zip'
    $url = "https://codeload.github.com/$Repo/zip/refs/heads/$Branch"
    $old = $ProgressPreference
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    $ProgressPreference = $old
    Expand-Archive -Path $zip -DestinationPath $tmp -Force

    $src = Get-ChildItem -Path $tmp -Directory | Where-Object { $_.Name -like 'notelint-*' } | Select-Object -First 1
    if (-not $src) { Die "Unexpected archive layout." }
    Write-Ok "Downloaded"

    # --------------------------------------------------------------- the base
    Write-Step "Creating the knowledge base"

    if ((Test-Path $Base) -and (Get-ChildItem $Base -Force -ErrorAction SilentlyContinue)) {
        Write-Warn "$Base already exists and is not empty."
        Write-Dim "Existing files are left untouched; only missing pieces are added."
    } else {
        New-Item -ItemType Directory -Path $Base -Force | Out-Null
        Write-Ok "Created $Base"
    }

    New-Item -ItemType Directory -Path (Join-Path $Base 'tools') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $Base 'templates') -Force | Out-Null

    $tools = @{
        'notelint.py'       = 'notelint.py'
        'tools\syncguard.py' = 'syncguard.py'
        'tools\power.py'     = 'power.py'
    }
    foreach ($rel in $tools.Keys) {
        $dst = Join-Path $Base ('tools\' + $tools[$rel])
        if (Test-Path $dst) {
            Write-Dim ("kept existing tools\" + $tools[$rel])
        } else {
            Copy-Item (Join-Path $src.FullName $rel) $dst
        }
    }
    Write-Ok "Tools installed in $Base\tools\"

    $tpl = Join-Path $Base 'templates\note.md'
    if (Test-Path $tpl) { Write-Dim "kept existing templates\note.md" }
    else { Copy-Item (Join-Path $src.FullName 'templates\note.md') $tpl }

    $proto = Join-Path $Base 'PROTOCOL.md'
    if (Test-Path $proto) { Write-Dim "kept existing PROTOCOL.md" }
    else { Copy-Item (Join-Path $src.FullName 'docs\PROTOCOL.md') $proto }
    Write-Ok "Protocol and note template in place"

    # ----------------------------------------------------------- first project
    $projNotes = Join-Path $Base "$FirstProject\notes"
    if (Test-Path $projNotes) {
        Write-Dim "project '$FirstProject' already exists"
    } else {
        New-Item -ItemType Directory -Path $projNotes -Force | Out-Null
        $today = Get-Date -Format 'yyyy-MM-dd'
        $note = @"
---
title: What $FirstProject is
type: fact
project: $FirstProject
status: current
created: $today
reviewed: $today
expires:
evidence: []
links:
  depends-on: []
  supersedes: []
  blocks: []
  related: []
---

## What this is

Replace this with one paragraph saying what $FirstProject actually is, for
someone who has never seen it. Not what you plan to do with it - what it is
today.

## How to verify

Say the command, the path or the screen that proves the sentence above is still
true. If you cannot name one, this note is not ``current``: set status to
``unverified`` and make checking it the first job.

A verification method that does not work is worse than none, because the next
reader trusts it.
"@
        Set-Content -Path (Join-Path $projNotes 'what-this-project-is.md') -Value $note -Encoding UTF8
        Write-Ok "First project created: $FirstProject"
    }

    # ------------------------------------------------------------- agent skill
    Write-Step "Claude Code skill"

    $skillSrc = Join-Path $src.FullName 'skills\notelint'
    $skillDst = Join-Path $HOME '.claude\skills\notelint'
    if (Test-Path $skillSrc) {
        if (Test-Path $skillDst) {
            Write-Dim "skill already installed at $skillDst"
        } else {
            New-Item -ItemType Directory -Path (Split-Path $skillDst) -Force | Out-Null
            Copy-Item $skillSrc $skillDst -Recurse
            Write-Ok "Skill installed at $skillDst"
            Write-Dim "Claude Code will pick it up on the next session."
        }
    } else {
        Write-Warn "No skill directory in the archive; skipped."
    }

    # -------------------------------------------------------------- first run
    Write-Step "First run"

    Push-Location $Base
    try {
        & ([scriptblock]::Create("$py tools\notelint.py ."))
        $rc = $LASTEXITCODE
    } finally {
        Pop-Location
    }

    Write-Host ""
    if ($rc -eq 1) {
        Write-Dim "Exit code 1 means it found something - that is the tool working."
    }

    # ------------------------------------------------------------- what next
    Write-Step "Done"
    Write-Host ""
    Write-Host "  Your base:  $Base"
    Write-Host ""
    Write-Host "  Lint it, and regenerate INDEX.md / OPEN.md:"
    Write-Host "    cd `"$Base`"; $py tools\notelint.py ." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Just look, change nothing:"
    Write-Host "    $py tools\notelint.py . --report-only" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Working from more than one machine? See docs/SYNC.md in the repo:"
    Write-Host "    $py tools\syncguard.py . --status" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Next: write your first real note. Copy templates\note.md into"
    Write-Host "  $FirstProject\notes\ and fill it in. Then run the linter again."
    Write-Host ""
}
finally {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
