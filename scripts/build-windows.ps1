# GaugePunk Windows 打包脚本 - 生成单文件 EXE.
#
# 用法 (PowerShell):
#     .\scripts\build-windows.ps1
#
# 前置: gaugepunk conda 环境已建好 (含 pyinstaller). 见 environment.yml.

$ErrorActionPreference = "Stop"

# 切到仓库根目录
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# 优先使用 gaugepunk 环境的 python.exe; 兜底用 PATH 里的 python
$EnvPython = "$env:USERPROFILE\.conda\envs\gaugepunk\python.exe"
if (Test-Path $EnvPython) {
    $Python = $EnvPython
} else {
    $Python = "python"
}
Write-Host "[build] using python: $Python"

# 清理旧产物
if (Test-Path dist)  { Remove-Item dist  -Recurse -Force }
if (Test-Path build) { Remove-Item build -Recurse -Force }

# 跑 PyInstaller
& $Python -m PyInstaller gaugepunk.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller 失败 (exit=$LASTEXITCODE)"
    exit $LASTEXITCODE
}

$Exe = Join-Path $Root "dist\GaugePunk.exe"
if (-not (Test-Path $Exe)) {
    Write-Error "没找到产物 $Exe"
    exit 1
}

$Size = "{0:N1} MB" -f ((Get-Item $Exe).Length / 1MB)
Write-Host ""
Write-Host "[build] OK -> $Exe  ($Size)"
Write-Host "[build] 双击启动, 第一次会在 EXE 同目录生成 config.yaml 和 gaugepunk.log"
