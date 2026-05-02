<#
    Standalone preflight check. Prints status and exits 0 if everything is ready.
#>

function Test-Cmd { param($N) [bool](Get-Command $N -ErrorAction SilentlyContinue) }

$results = @(
    @{ name = "Docker Desktop"; cmd = "docker"; install = "https://www.docker.com/products/docker-desktop/" }
    @{ name = "Node.js 20 LTS"; cmd = "node"; install = "https://nodejs.org/" }
    @{ name = "Claude Code CLI"; cmd = "claude"; install = "npm install -g @anthropic-ai/claude-code" }
    @{ name = "git"; cmd = "git"; install = "https://git-scm.com/download/win" }
)

$missing = 0
foreach ($r in $results) {
    if (Test-Cmd $r.cmd) {
        Write-Host ("  [ OK ] {0}" -f $r.name) -ForegroundColor Green
    } else {
        Write-Host ("  [MISS] {0} -> {1}" -f $r.name, $r.install) -ForegroundColor Yellow
        $missing++
    }
}

if ($missing -eq 0) {
    Write-Host "`nAll prerequisites are installed." -ForegroundColor Green
    exit 0
} else {
    Write-Host ("`n{0} prerequisite(s) missing. Install them and re-run." -f $missing) -ForegroundColor Yellow
    exit 1
}
