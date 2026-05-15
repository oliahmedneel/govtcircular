# Remove nested .git folder in hugo-site
$target = "D:\JobSite\hugo-site\.git"
if (Test-Path $target) {
    # Try to remove
    try {
        Remove-Item -Recurse -Force $target -ErrorAction Stop
        Write-Host "REMOVED SUCCESSFULLY"
    } catch {
        Write-Host "Direct removal failed: $_"
        # Try alternative - rename first
        try {
            Rename-Item $target "git_backup_temp" -Force
            Remove-Item -Recurse -Force "D:\JobSite\hugo-site\git_backup_temp" -ErrorAction Stop
            Write-Host "RENAMED AND REMOVED"
        } catch {
            Write-Host "STILL FAILED: $_"
        }
    }
} else {
    Write-Host "ALREADY GONE"
}