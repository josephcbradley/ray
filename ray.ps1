<#
.SYNOPSIS
ray: Wrapper for 'uv init' that configures the project to use the local ray mirror.
#>

# Attempt to find the target directory from the arguments
$TargetDir = "."
foreach ($arg in $args) {
    if (-Not $arg.StartsWith("-")) {
        $TargetDir = $arg
        break
    }
}

# Run uv init with all passed arguments
uv init @args

if ($LASTEXITCODE -eq 0) {
    # Resolve the correct path to pyproject.toml
    $TomlPath = Join-Path -Path $TargetDir -ChildPath "pyproject.toml"
    
    if (Test-Path $TomlPath) {
        $Config = @"

[[tool.uv.index]]
url="http://localhost:8080/simple/"
default=true

[tool.uv]
environments = [
    "sys_platform == 'win32'"
]
"@
        Add-Content -Path $TomlPath -Value $Config
        Write-Host "Successfully configured $TomlPath for local ray mirror (win32)." -ForegroundColor Green
    } else {
        Write-Host "Warning: Could not find pyproject.toml at $TomlPath" -ForegroundColor Yellow
    }
} else {
    Write-Host "uv init failed." -ForegroundColor Red
    exit $LASTEXITCODE
}