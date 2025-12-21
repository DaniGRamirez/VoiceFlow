# Claude PTY Wrapper - Shim Installation Script
#
# This script adds the shim directory to the user's PATH so that
# 'claude' commands are intercepted by the wrapper.
#
# Usage:
#   .\install-shim.ps1           - Install the shim
#   .\install-shim.ps1 -Uninstall - Remove the shim from PATH
#
# After installation:
#   - 'claude' will go through the wrapper
#   - Set CLAUDE_MON_DISABLE=1 to bypass the wrapper

param(
    [switch]$Uninstall
)

$shimDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$shimPath = Join-Path $shimDir "claude.cmd"

# Get current user PATH
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
$pathParts = $userPath -split ';' | Where-Object { $_ -ne '' }

if ($Uninstall) {
    # Remove shim directory from PATH
    $newParts = $pathParts | Where-Object { $_ -ne $shimDir }

    if ($newParts.Count -lt $pathParts.Count) {
        $newPath = $newParts -join ';'
        [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
        Write-Host "Removed $shimDir from PATH" -ForegroundColor Green
        Write-Host "Please restart your terminal for changes to take effect."
    } else {
        Write-Host "Shim directory was not in PATH" -ForegroundColor Yellow
    }
} else {
    # Check if shim directory is already in PATH
    if ($pathParts -contains $shimDir) {
        Write-Host "Shim directory already in PATH" -ForegroundColor Yellow
    } else {
        # Add shim directory to the beginning of PATH (so it takes precedence)
        $newPath = "$shimDir;$userPath"
        [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
        Write-Host "Added $shimDir to PATH" -ForegroundColor Green
    }

    # Verify installation
    Write-Host ""
    Write-Host "Installation complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Please restart your terminal, then test with:" -ForegroundColor Cyan
    Write-Host "  claude --version"
    Write-Host ""
    Write-Host "Escape hatch (bypass wrapper):" -ForegroundColor Cyan
    Write-Host "  `$env:CLAUDE_MON_DISABLE = 1"
    Write-Host "  claude --version"
    Write-Host ""
    Write-Host "To uninstall:" -ForegroundColor Cyan
    Write-Host "  .\install-shim.ps1 -Uninstall"
}
