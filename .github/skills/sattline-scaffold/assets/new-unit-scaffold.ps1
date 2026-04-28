param(
    [Parameter(Mandatory = $true)]
    [string]$MainLibName,

    [Parameter(Mandatory = $true)]
    [string]$SupportLibName,

    [Parameter(Mandatory = $true)]
    [string]$ProgramName,

    [string]$UnitName = "T11A",

    [string]$UnitModuleTypeName = "",

    [string]$RepoRoot = "."
)

if ([string]::IsNullOrWhiteSpace($UnitModuleTypeName)) {
    $UnitModuleTypeName = $UnitName
}

if ($UnitName.Length -gt 20) {
    throw "UnitName exceeds 20 characters: $UnitName"
}

if ($UnitModuleTypeName.Length -gt 20) {
    throw "UnitModuleTypeName exceeds 20 characters: $UnitModuleTypeName"
}

if ($MainLibName.Length -gt 20) {
    throw "MainLibName exceeds 20 characters: $MainLibName"
}

if ($SupportLibName.Length -gt 20) {
    throw "SupportLibName exceeds 20 characters: $SupportLibName"
}

if ($ProgramName.Length -gt 20) {
    throw "ProgramName exceeds 20 characters: $ProgramName"
}

$unitInvocationName = $UnitName
if ($unitInvocationName -match '^[0-9]') {
    $unitInvocationName = "U$unitInvocationName"
}

if ($unitInvocationName.Length -gt 20) {
    throw "Unit invocation identifier exceeds 20 characters after normalization: $unitInvocationName"
}

$repo = (Resolve-Path -Path $RepoRoot).Path
$templateBase = Join-Path $repo "Libs/HA/NNELib/NNEStart"
$projectDir = Join-Path $repo "Libs/HA/ProjectLib"
$unitDir = Join-Path $repo "Libs/HA/UnitLib"

$sourceProgram = $null
if (Test-Path -Path "$templateBase.s") {
    $sourceProgram = "$templateBase.s"
} elseif (Test-Path -Path "$templateBase.x") {
    $sourceProgram = "$templateBase.x"
} else {
    throw "Missing NNEStart donor source. Expected one of: $templateBase.s or $templateBase.x"
}

$sourceDeps = $null
if (Test-Path -Path "$templateBase.l") {
    $sourceDeps = "$templateBase.l"
} elseif (Test-Path -Path "$templateBase.z") {
    $sourceDeps = "$templateBase.z"
} else {
    throw "Missing NNEStart donor dependency list. Expected one of: $templateBase.l or $templateBase.z"
}

$targets = @(
    @{ Name = $MainLibName; Dir = $projectDir },
    @{ Name = $SupportLibName; Dir = $projectDir },
    @{ Name = $ProgramName; Dir = $unitDir }
)

$sourceByExtension = @{
    s = $sourceProgram
    l = $sourceDeps
}

$extensions = @("s", "l")

foreach ($target in $targets) {
    foreach ($ext in $extensions) {
        $src = $sourceByExtension[$ext]
        $dst = Join-Path $target.Dir ("{0}.{1}" -f $target.Name, $ext)
        Copy-Item -Path $src -Destination $dst -Force

        $content = Get-Content -Path $dst -Raw
        $content = $content -replace 'name:\s*NNEStart', ("name: {0}" -f $target.Name)

        if ($target.Name -eq $ProgramName -and $ext -eq "s") {
            $content = $content -replace 'Name\s*=>\s*"NNEStart"', ("Name => `"{0}`"" -f $ProgramName)
            $content = $content -replace '\bT11A\s+Invocation\b', ("{0} Invocation" -f $unitInvocationName)
        }

        Set-Content -Path $dst -Value $content -NoNewline
    }

    $graphicsPath = Join-Path $target.Dir ("{0}.g" -f $target.Name)
    Set-Content -Path $graphicsPath -Value $null -NoNewline
}

Write-Host "Scaffold created (bootstrap only; donor extraction still required):"
Write-Host "  ProjectLib/$MainLibName.{g,l,s}"
Write-Host "  ProjectLib/$SupportLibName.{g,l,s}"
Write-Host "  UnitLib/$ProgramName.{g,l,s}"
Write-Host "  Donor program source: $([System.IO.Path]::GetFileName($sourceProgram))"
Write-Host "  Donor dependency source: $([System.IO.Path]::GetFileName($sourceDeps))"
if ($unitInvocationName -ne $UnitName) {
    Write-Host "  Note: unit invocation identifier '$UnitName' is not legal at start; using '$unitInvocationName'."
}
Write-Host ""
Write-Host "BOOTSTRAP ONLY - NOT A COMPLETE UNIT"
Write-Host "Do not stop after this script. A valid result must still look like a donor-derived extraction of T11A from NNEStart."
Write-Host "Do not replace donor control body with a thin wrapper. Preserve donor UnitControl and Operations subtree."
Write-Host ""
Write-Host "Mandatory next steps (NNEStart extraction flow):"
Write-Host "  1) Keep program utility baseline in UnitLib/$ProgramName.s (OPStationUtility, TimeDistribution, ProgramUnitUtility)."
Write-Host "  2) Extract real '$unitInvocationName' donor body from NNEStart into ProjectLib/$MainLibName.s. Do not replace it with a miniature stand-in."
Write-Host "  3) Convert moved block to exported moduletype '$UnitModuleTypeName' in main library."
Write-Host "  4) Replace inline unit in UnitLib/$ProgramName.s with invocation of '$UnitModuleTypeName'."
Write-Host "  5) Preserve inline donor UnitControl, Operations, startup panels, phase paths, and batch-control wiring inside the extracted main-library unit body."
Write-Host "  6) Move all remaining donor type definitions and support modules into ProjectLib/$SupportLibName.s."
Write-Host "     Keep donor support surfaces such as T11AInlet/T11AOutlet/T11AAgitator/T11ACooling, related state modules, and CMD/DV/shared-input records."
Write-Host "  7) Keep Program generic donor modules from NNEStart; do not delete donor content in scaffold flow."
Write-Host "  8) Keep Program.l depending on $MainLibName, keep MainLib.l depending on $SupportLibName, and ensure each target has an empty .g file."
Write-Host "  9) Adapt only equipment-module names, labels, addresses, and unit-specific values to requested unit type."
Write-Host " 10) Preserve ModuleDef/GraphObjects blocks while extracting. TextObject belongs in GraphObjects, not as a submodule invocation."
Write-Host " 11) Validate with sattlint syntax-check for touched .s files and verify donor-fidelity by comparing against NNEStart.x T11A surface."
Write-Host " 12) Stop if resulting main library lacks donor UnitControl or operations tree; scaffold is incomplete."
Write-Host ""
Write-Host "SattLine constraints to keep in mind:"
Write-Host "  - Identifier length limit: 20 characters."
Write-Host "  - Every MODULEDEFINITION body needs ModuleDef."
Write-Host "  - Syntax-check passing is necessary but not sufficient; donor UnitControl/Operations must still be present."
