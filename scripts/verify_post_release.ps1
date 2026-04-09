param(
  [ValidateSet("pypi", "wheel")]
  [string]$Mode = "pypi",
  [string]$PackageName = "deepwiki-cli",
  [string]$Version = "",
  [string]$WheelPath = "",
  [string]$WorkDir = ".",
  [string]$RepoForOfflineGenerate = ".",
  [string]$PythonExe = "py",
  [string]$PythonVersionArg = "-3.14"
)

$ErrorActionPreference = "Stop"

$resolvedWorkDir = Resolve-Path $WorkDir
$venvDir = Join-Path $resolvedWorkDir ".venv_release_verify"
if (Test-Path $venvDir) {
  Remove-Item -Recurse -Force $venvDir
}

& $PythonExe $PythonVersionArg -m venv "$venvDir"

$venvPython = Join-Path $venvDir "Scripts\python.exe"

& $venvPython -m pip install --upgrade pip

if ($Mode -eq "wheel") {
  if ([string]::IsNullOrWhiteSpace($WheelPath)) {
    throw "WheelPath is required in wheel mode."
  }
  $resolvedWheel = Resolve-Path $WheelPath
  & $venvPython -m pip install "$resolvedWheel"
}
else {
  if ([string]::IsNullOrWhiteSpace($Version)) {
    & $venvPython -m pip install $PackageName
  }
  else {
    & $venvPython -m pip install "$PackageName==$Version"
  }
}

& $venvPython -m deepwiki --help
& $venvPython -m deepwiki version
& $venvPython -m deepwiki generate $RepoForOfflineGenerate --offline
