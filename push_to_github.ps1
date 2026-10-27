# Push to GitHub
$git = 'E:\PortableGit\cmd\git.exe'
Set-Location E:\CampusTodo

Write-Host "=== 1. Configure remote ===" -ForegroundColor Cyan
$existing = & $git remote 2>$null
if ($existing -contains 'origin') {
    & $git remote set-url origin https://github.com/Ice-one531/campus-todo.git
    Write-Host "  origin updated" -ForegroundColor Green
} else {
    & $git remote add origin https://github.com/Ice-one531/campus-todo.git
    Write-Host "  origin added" -ForegroundColor Green
}
& $git remote -v

Write-Host ""
Write-Host "=== 2. Push ===" -ForegroundColor Cyan
Write-Host "  A browser window may open. Login as Ice-one531 and click Authorize." -ForegroundColor Yellow
& $git push -u origin main

Write-Host ""
Write-Host "=== 3. Result ===" -ForegroundColor Cyan
& $git log --oneline -1
& $git remote -v
Write-Host ""
Write-Host "Done. Press any key to close."
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')