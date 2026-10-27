# 一键 push 到 GitHub
$git = 'E:\PortableGit\cmd\git.exe'
Set-Location E:\CampusTodo

Write-Host '=== 1. 配置 remote ===' -ForegroundColor Cyan
$existing = & $git remote 2>$null
if ($existing -contains 'origin') {
    & $git remote set-url origin https://github.com/Ice-one531/campus-todo.git
    Write-Host '  已更新 origin' -ForegroundColor Green
} else {
    & $git remote add origin https://github.com/Ice-one531/campus-todo.git
    Write-Host '  已添加 origin' -ForegroundColor Green
}
& $git remote -v

Write-Host ''
Write-Host '=== 2. push ===' -ForegroundColor Cyan
Write-Host '  如果弹出浏览器授权页，登录 Ice-one531 并点 Authorize' -ForegroundColor Yellow
& $git push -u origin main

Write-Host ''
Write-Host '=== 3. 结果 ===' -ForegroundColor Cyan
& $git log --oneline -1
& $git remote -v