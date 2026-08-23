[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$lane = Split-Path -Parent $PSScriptRoot
$releaseId = 'R011-B007-v2026.08.23.1'
$boundaryId = 'R011-B007'
$release = Join-Path $lane ('release\zenodo\' + $releaseId)
$releaseParent = Split-Path -Parent $release
$stagingLeaf = '.' + $releaseId + '.package-staging'
$staging = Join-Path $releaseParent $stagingLeaf
$evidenceDirectory = Join-Path $lane 'qa\b007-zenodo'
$packageReceiptPath = Join-Path $evidenceDirectory ('PACKAGE_RECEIPT_' + $releaseId + '.json')
$transactionLockPath = Join-Path $evidenceDirectory ('.' + $releaseId + '.lock')
$sourceSnapshot = Join-Path $lane 'qa\b007-build\source-snapshot-v8'
$snapshotManifestPath = Join-Path $lane 'qa\b007-build\R011-B007_SNAPSHOT_MANIFEST_V8.tsv'
$admittedPdfSource = Join-Path $lane 'output\pdf\statistika-berbasis-data-batas-R011-B007.pdf'
$releasePdfSource = Join-Path $lane 'qa\b007-zenodo\reader-optimization\reader-pass1.pdf'
$readerOptimizationReceiptPath = Join-Path $lane 'qa\b007-zenodo\READER_OPTIMIZATION_RECEIPT_R011-B007.json'
$backendExportsPath = Join-Path $lane 'backend\exports'
$backendManifestPath = Join-Path $backendExportsPath 'manifest.json'
$backendReceiptPath = Join-Path $lane 'qa\b007-backend\BACKEND_VALIDATION_RECEIPT_R011-B007.json'
$finalGateInputsPath = Join-Path $lane 'qa\b007-backend\R011-B007_FINAL_GATE_INPUTS.json'
$boundaryReceiptPath = Join-Path $lane 'qa\R011-B007_BOUNDARY_RECEIPT.json'
$admissionLockPath = Join-Path $lane 'qa\b007-backend\.R011-B007-admission.lock'
$admissionJournalPath = Join-Path $lane 'qa\b007-backend\R011-B007_ADMISSION_TRANSACTION_JOURNAL.json'
$sourceExclusion = 'ch_intro_to_data/figures/eoce/migraine_and_acupuncture_intro/earacupuncture.pdf'
$fixedTimestamp = [DateTimeOffset]::Parse('2026-08-23T00:00:00Z')
$maximumReleaseBytes = [int64]500000000
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)

$staticMetadataNames = @(
    'CITATION.cff',
    'LICENSES_AND_ATTRIBUTION.md',
    'README_RELEASE.md',
    'ZENODO_METADATA.json'
)
$generatedNames = @(
    '00_STATISTIKA_BERBASIS_DATA_ID_R011-B007_WORKING_READER.pdf',
    '01_STATISTIKA_BERBASIS_DATA_ID_R011-B007_EDITABLE_SOURCE.zip',
    '02_STATISTIKA_BERBASIS_DATA_ID_R011-B007_MODULAR_BACKEND.zip',
    'RELEASE_MANIFEST.json',
    'SHA256SUMS.txt'
)
$expectedReleaseNames = @($generatedNames + $staticMetadataNames)

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-Sha256Bytes([byte[]]$Bytes) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Get-ExactFileIdentity([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Missing exact file: $Path" }
    return [pscustomobject]@{
        bytes = [int64](Get-Item -LiteralPath $Path).Length
        sha256 = Get-Sha256 $Path
    }
}

function Assert-Identity([string]$Path, [object]$Expected, [string]$Label) {
    $actual = Get-ExactFileIdentity $Path
    if ($actual.bytes -ne [int64]$Expected.bytes -or $actual.sha256 -cne [string]$Expected.sha256) {
        throw "$Label exact byte identity mismatch"
    }
    return $actual
}

function Get-OrdinalSortedStrings([object[]]$Values) {
    [string[]]$result = @($Values | ForEach-Object { [string]$_ })
    [Array]::Sort($result, [System.StringComparer]::Ordinal)
    return $result
}

function Assert-ExactNames([object[]]$Actual, [object[]]$Expected, [string]$Label) {
    [string[]]$actualSorted = @(Get-OrdinalSortedStrings $Actual)
    [string[]]$expectedSorted = @(Get-OrdinalSortedStrings $Expected)
    if (($actualSorted -join "`n") -cne ($expectedSorted -join "`n")) {
        throw "$Label inventory mismatch; actual=[$($actualSorted -join ', ')]; expected=[$($expectedSorted -join ', ')]"
    }
}

function Get-RelativeFileRecords([string]$Root) {
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) { throw "Missing tree root: $Root" }
    $rootItem = Get-Item -LiteralPath $Root
    $records = @(
        Get-ChildItem -LiteralPath $rootItem.FullName -Recurse -File -Force | ForEach-Object {
            $relative = $_.FullName.Substring($rootItem.FullName.Length).TrimStart('\', '/').Replace('\', '/')
            [pscustomobject]@{ Relative = $relative; Source = $_.FullName; Bytes = [int64]$_.Length }
        }
    )
    $byPath = [System.Collections.Generic.Dictionary[string, object]]::new([System.StringComparer]::Ordinal)
    foreach ($record in $records) {
        if ($byPath.ContainsKey($record.Relative)) { throw "Duplicate relative path in tree: $($record.Relative)" }
        $byPath.Add($record.Relative, $record)
    }
    [string[]]$names = @(Get-OrdinalSortedStrings @($byPath.Keys))
    return @($names | ForEach-Object { $byPath[$_] })
}

function Get-TreeInventoryIdentity([string]$Root) {
    $records = @(Get-RelativeFileRecords $Root)
    $builder = [System.Text.StringBuilder]::new()
    [int64]$total = 0
    foreach ($record in $records) {
        $hash = Get-Sha256 $record.Source
        [void]$builder.Append($record.Relative).Append("`t").Append($record.Bytes).Append("`t").Append($hash).Append("`n")
        $total += $record.Bytes
    }
    return [pscustomobject]@{
        file_count = $records.Count
        bytes = $total
        sha256 = Get-Sha256Bytes ($utf8NoBom.GetBytes($builder.ToString()))
    }
}

function Get-SnapshotZipSelection([string]$Root, [string]$ManifestPath, [string]$Prefix, [string]$ExcludedRelativePath) {
    $records = @(Get-RelativeFileRecords $Root)
    $actualByPath = [System.Collections.Generic.Dictionary[string, object]]::new([System.StringComparer]::Ordinal)
    foreach ($record in $records) { $actualByPath.Add($record.Relative, $record) }

    $manifestByPath = [System.Collections.Generic.Dictionary[string, object]]::new([System.StringComparer]::Ordinal)
    foreach ($line in Get-Content -LiteralPath $ManifestPath) {
        if ($line -notmatch '^([^\t]+)\t([0-9]+)\t([0-9a-f]{64})$') { throw "Invalid source snapshot manifest line: $line" }
        $relative = $Matches[1]
        if ($relative.StartsWith('/') -or $relative.Contains('\') -or @($relative.Split('/') | Where-Object { $_ -eq '..' }).Count -ne 0) {
            throw "Unsafe source snapshot manifest path: $relative"
        }
        if ($manifestByPath.ContainsKey($relative)) { throw "Duplicate source snapshot manifest path: $relative" }
        $manifestByPath.Add($relative, [pscustomobject]@{ Bytes = [int64]$Matches[2]; Sha256 = $Matches[3] })
    }
    Assert-ExactNames -Actual @($actualByPath.Keys) -Expected @($manifestByPath.Keys) -Label 'Source snapshot versus admitted snapshot manifest'
    if (-not $manifestByPath.ContainsKey($ExcludedRelativePath)) { throw 'The one authorized source exclusion is absent from the admitted snapshot' }

    $items = @()
    $excluded = $null
    [string[]]$names = @(Get-OrdinalSortedStrings @($manifestByPath.Keys))
    foreach ($relative in $names) {
        $actual = $actualByPath[$relative]
        $expected = $manifestByPath[$relative]
        $hash = Get-Sha256 $actual.Source
        if ($actual.Bytes -ne $expected.Bytes -or $hash -cne $expected.Sha256) { throw "Source snapshot identity mismatch: $relative" }
        $item = [pscustomobject]@{
            Source = $actual.Source
            Entry = ($Prefix.TrimEnd('/').Replace('\', '/') + '/' + $relative)
            Relative = $relative
            Bytes = $actual.Bytes
            Sha256 = $hash
        }
        if ($relative -ceq $ExcludedRelativePath) { $excluded = $item } else { $items += $item }
    }
    if ($null -eq $excluded -or $items.Count -ne ($names.Count - 1)) { throw 'Source publication exclusion was not exactly one file' }
    return [pscustomobject]@{ Items = $items; Excluded = $excluded; SnapshotEntries = $names.Count }
}

function Get-TreeZipItems([string]$Root, [string]$Prefix) {
    return @(
        Get-RelativeFileRecords $Root | ForEach-Object {
            [pscustomobject]@{
                Source = $_.Source
                Entry = ($Prefix.TrimEnd('/').Replace('\', '/') + '/' + $_.Relative)
                Relative = $_.Relative
                Bytes = $_.Bytes
                Sha256 = Get-Sha256 $_.Source
            }
        }
    )
}

function New-ZipItem([string]$Source, [string]$Entry) {
    $identity = Get-ExactFileIdentity $Source
    return [pscustomobject]@{
        Source = (Get-Item -LiteralPath $Source).FullName
        Entry = $Entry.Replace('\', '/')
        Relative = $Entry.Replace('\', '/')
        Bytes = $identity.bytes
        Sha256 = $identity.sha256
    }
}

function New-DeterministicZip([string]$Path, [object[]]$Items) {
    if (Test-Path -LiteralPath $Path) { throw "Staging ZIP already exists: $Path" }
    $byEntry = [System.Collections.Generic.Dictionary[string, object]]::new([System.StringComparer]::Ordinal)
    foreach ($item in $Items) {
        if ($byEntry.ContainsKey([string]$item.Entry)) { throw "Duplicate ZIP entry: $($item.Entry)" }
        $byEntry.Add([string]$item.Entry, $item)
    }
    [string[]]$entries = @(Get-OrdinalSortedStrings @($byEntry.Keys))
    $fileStream = [System.IO.File]::Open($Path, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    try {
        $archive = [System.IO.Compression.ZipArchive]::new($fileStream, [System.IO.Compression.ZipArchiveMode]::Create, $false, $utf8NoBom)
        try {
            foreach ($name in $entries) {
                $item = $byEntry[$name]
                $entry = $archive.CreateEntry($name, [System.IO.Compression.CompressionLevel]::Optimal)
                $entry.LastWriteTime = $fixedTimestamp
                $sourceStream = [System.IO.File]::OpenRead($item.Source)
                try {
                    $entryStream = $entry.Open()
                    try { $sourceStream.CopyTo($entryStream) } finally { $entryStream.Dispose() }
                } finally { $sourceStream.Dispose() }
            }
        } finally { $archive.Dispose() }
    } finally { $fileStream.Dispose() }
}

function Test-ZipExact([string]$Path, [object[]]$Items) {
    $expected = [System.Collections.Generic.Dictionary[string, object]]::new([System.StringComparer]::Ordinal)
    foreach ($item in $Items) {
        if ($expected.ContainsKey([string]$item.Entry)) { throw "Duplicate expected ZIP entry: $($item.Entry)" }
        $expected.Add([string]$item.Entry, [pscustomobject]@{ Bytes = [int64]$item.Bytes; Sha256 = [string]$item.Sha256 })
    }
    $fileStream = [System.IO.File]::OpenRead($Path)
    try {
        $archive = [System.IO.Compression.ZipArchive]::new($fileStream, [System.IO.Compression.ZipArchiveMode]::Read, $false, $utf8NoBom)
        try {
            if ($archive.Entries.Count -ne $expected.Count) { throw "ZIP entry count mismatch for $Path" }
            $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
            [int64]$sum = 0
            foreach ($entry in $archive.Entries) {
                if (-not $expected.ContainsKey($entry.FullName)) { throw "Unexpected ZIP entry $($entry.FullName)" }
                if (-not $seen.Add($entry.FullName)) { throw "Duplicate ZIP entry $($entry.FullName)" }
                $want = $expected[$entry.FullName]
                if ($entry.Length -ne $want.Bytes) { throw "ZIP entry size mismatch: $($entry.FullName)" }
                $sha = [System.Security.Cryptography.SHA256]::Create()
                try {
                    $stream = $entry.Open()
                    try { $digest = $sha.ComputeHash($stream) } finally { $stream.Dispose() }
                } finally { $sha.Dispose() }
                $actual = ([System.BitConverter]::ToString($digest)).Replace('-', '').ToLowerInvariant()
                if ($actual -cne $want.Sha256) { throw "ZIP entry hash mismatch: $($entry.FullName)" }
                $sum += $entry.Length
            }
            if ($seen.Count -ne $expected.Count) { throw "Missing ZIP entry in $Path" }
            return [pscustomobject]@{
                filename = Split-Path -Leaf $Path
                entries = $archive.Entries.Count
                uncompressed_bytes = $sum
                zip_bytes = [int64](Get-Item -LiteralPath $Path).Length
                sha256 = Get-Sha256 $Path
                exact_path_size_sha256_verification = 'passed'
            }
        } finally { $archive.Dispose() }
    } finally { $fileStream.Dispose() }
}

function Remove-ExactStagingDirectory([string]$Path, [string]$ExpectedParent, [string]$ExpectedLeaf) {
    $full = [System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
    $parent = [System.IO.Path]::GetFullPath($ExpectedParent).TrimEnd('\', '/')
    if (-not [System.StringComparer]::OrdinalIgnoreCase.Equals([System.IO.Path]::GetDirectoryName($full), $parent) -or
        -not [System.StringComparer]::Ordinal.Equals([System.IO.Path]::GetFileName($full), $ExpectedLeaf)) {
        throw "Unsafe staging cleanup target: $full"
    }
    if (Test-Path -LiteralPath $full) { Remove-Item -LiteralPath $full -Recurse -Force }
}

function Write-AtomicUtf8Json([string]$Path, [object]$Value) {
    $temporary = $Path + '.tmp'
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
    [System.IO.File]::WriteAllText($temporary, ($Value | ConvertTo-Json -Depth 12) + "`n", $utf8NoBom)
    Move-Item -LiteralPath $temporary -Destination $Path -Force
}

function Enter-TransactionLock([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        try {
            $stale = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
            $stale.Dispose()
            Remove-Item -LiteralPath $Path -Force
        } catch {
            throw 'Another B007 package/publication transaction holds the exact lock'
        }
    }
    return [System.IO.File]::Open($Path, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
}

foreach ($required in @($release, $sourceSnapshot, $backendExportsPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Container)) { throw "Missing required directory: $required" }
}
foreach ($required in @($admittedPdfSource, $releasePdfSource, $readerOptimizationReceiptPath, $snapshotManifestPath, $backendManifestPath, $backendReceiptPath, $finalGateInputsPath, $boundaryReceiptPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing admitted release input: $required" }
}
foreach ($blocked in @($admissionLockPath, $admissionJournalPath)) {
    if (Test-Path -LiteralPath $blocked) { throw "Admission transaction residue is present: $blocked" }
}

$currentReleaseNames = @(Get-ChildItem -LiteralPath $release -File -Force | ForEach-Object Name)
$unexpectedReleaseNames = @($currentReleaseNames | Where-Object { $_ -notin $expectedReleaseNames })
if ($unexpectedReleaseNames.Count -ne 0) { throw "Unexpected release files must not be packaged: $($unexpectedReleaseNames -join ', ')" }
foreach ($name in $staticMetadataNames) {
    if (-not (Test-Path -LiteralPath (Join-Path $release $name) -PathType Leaf)) { throw "Missing static release metadata: $name" }
}

if (-not (Test-Path -LiteralPath $evidenceDirectory -PathType Container)) {
    [void](New-Item -ItemType Directory -Path $evidenceDirectory)
}
$lockStream = Enter-TransactionLock $transactionLockPath
try {
    $boundaryReceipt = Get-Content -LiteralPath $boundaryReceiptPath -Raw | ConvertFrom-Json
    if ([string]$boundaryReceipt.'$schema' -cne 'r011-b007-boundary-receipt/v1' -or
        [string]$boundaryReceipt.boundary_id -cne $boundaryId -or
        [string]$boundaryReceipt.base_boundary -cne 'R011-B006' -or
        [string]$boundaryReceipt.status -cne 'admitted_exact_pdf_and_backend' -or
        -not [bool]$boundaryReceipt.canonical_pdf_promoted -or
        -not [bool]$boundaryReceipt.live_backend_mutated -or
        -not [bool]$boundaryReceipt.promoted_pdf.readback_exact -or
        -not [bool]$boundaryReceipt.transaction.preflight_fail_closed -or
        -not [bool]$boundaryReceipt.transaction.boundary_receipt_written_only_after_backend_and_pdf_readback) {
        throw 'Boundary receipt is not the exact completed B007 admission authority'
    }
    $boundaryIdentity = Get-ExactFileIdentity $boundaryReceiptPath
    [void](Assert-Identity -Path $backendReceiptPath -Expected $boundaryReceipt.backend_validation_receipt -Label 'Backend validation receipt')
    [void](Assert-Identity -Path $finalGateInputsPath -Expected $boundaryReceipt.final_gate_inputs -Label 'Final gate inputs')
    [void](Assert-Identity -Path $admittedPdfSource -Expected $boundaryReceipt.promoted_pdf -Label 'Promoted PDF')
    [void](Assert-Identity -Path $backendManifestPath -Expected $boundaryReceipt.admitted_backend.manifest -Label 'Admitted backend manifest')

    $readerOptimization = Get-Content -LiteralPath $readerOptimizationReceiptPath -Raw | ConvertFrom-Json
    if ([string]$readerOptimization.schema -cne 'interlanguage.release-reader-optimization' -or
        [string]$readerOptimization.schema_version -cne '1.0.0' -or
        [string]$readerOptimization.boundary_id -cne $boundaryId -or
        [string]$readerOptimization.status -cne 'passed_lossless_deterministic_transport_optimization' -or
        -not [bool]$readerOptimization.deterministic_replay.byte_identical -or
        -not [bool]$readerOptimization.semantic_and_structure_checks.metadata_equal -or
        -not [bool]$readerOptimization.visual_replay.all_pixels_identical -or
        @($readerOptimization.visual_replay.pixel_differences).Count -ne 0 -or
        @($readerOptimization.errors).Count -ne 0 -or @($readerOptimization.blockers).Count -ne 0 -or
        [bool]$readerOptimization.credentials_present) {
        throw 'Reader optimization receipt is not the exact passed lossless transport authority'
    }
    [void](Assert-Identity -Path $admittedPdfSource -Expected $readerOptimization.admitted_reader -Label 'Optimization admitted-reader input')
    [void](Assert-Identity -Path $releasePdfSource -Expected $readerOptimization.optimized_reader -Label 'Optimized release reader')
    [void](Assert-Identity -Path (Join-Path $lane ([string]$readerOptimization.deterministic_replay.second_path)) -Expected $readerOptimization.deterministic_replay -Label 'Optimized release reader replay')
    if ([string]$readerOptimization.admitted_reader.sha256 -cne [string]$boundaryReceipt.promoted_pdf.sha256 -or
        [int]$readerOptimization.semantic_and_structure_checks.page_count_optimized -ne [int]$boundaryReceipt.promoted_pdf.page_count -or
        [string]$readerOptimization.semantic_and_structure_checks.document_language_optimized -cne 'id-ID') {
        throw 'Reader optimization receipt is not bound to the admitted B007 PDF semantics'
    }
    $readerOptimizationReceiptIdentity = Get-ExactFileIdentity $readerOptimizationReceiptPath

    $backendReceipt = Get-Content -LiteralPath $backendReceiptPath -Raw | ConvertFrom-Json
    if ([string]$backendReceipt.'$schema' -cne 'r011-b007-backend-validation-receipt/v1' -or
        [string]$backendReceipt.boundary_id -cne $boundaryId -or
        [string]$backendReceipt.base_boundary -cne 'R011-B006' -or
        [string]$backendReceipt.status -cne 'passed_isolated_final_backend_ready_for_admission' -or
        [bool]$backendReceipt.boundary_admitted -or [bool]$backendReceipt.promotion_performed -or [bool]$backendReceipt.live_backend_mutated -or
        [int]$backendReceipt.validator_checks_passed -ne [int]$backendReceipt.validator_checks_total -or
        [int]$backendReceipt.validator_checks_total -ne 23 -or
        [int]$backendReceipt.record_count -ne [int]$boundaryReceipt.admitted_backend.record_count -or
        [string]$backendReceipt.stage_inventory_sha256 -cne [string]$boundaryReceipt.admitted_backend.inventory.sha256) {
        throw 'Backend validation receipt is not the exact admitted B007 precursor'
    }

    $finalGate = Get-Content -LiteralPath $finalGateInputsPath -Raw | ConvertFrom-Json
    if ([string]$finalGate.schema_version -cne 'r011-b007-final-gate-inputs/1.0.0' -or
        [string]$finalGate.boundary_id -cne $boundaryId -or
        [string]$finalGate.status -cne 'supplied_exact_terminal_inputs' -or
        [string]$finalGate.gate.candidate -cne 'final-v8' -or
        [int]$finalGate.gate.page_count -ne [int]$boundaryReceipt.promoted_pdf.page_count -or
        [int]$finalGate.gate.severity_counts.P0 -ne 0 -or [int]$finalGate.gate.severity_counts.P1 -ne 0 -or
        [int]$finalGate.gate.severity_counts.P2 -ne 0 -or [int]$finalGate.gate.severity_counts.P3 -ne 0) {
        throw 'Final gate inputs do not prove the exact zero-severity final-v8 terminal gate'
    }
    [void](Assert-Identity -Path $snapshotManifestPath -Expected $finalGate.inputs.snapshot_manifest -Label 'Source snapshot manifest')
    if ([string]$finalGate.inputs.pdf.sha256 -cne [string]$boundaryReceipt.promoted_pdf.sha256 -or
        [int64]$finalGate.inputs.pdf.bytes -ne [int64]$boundaryReceipt.promoted_pdf.bytes -or
        [string]$finalGate.inputs.pass3_pdf.sha256 -cne [string]$finalGate.inputs.pdf.sha256) {
        throw 'Final gate PDF identity is not the promoted admitted PDF identity'
    }

    $backend = Get-Content -LiteralPath $backendManifestPath -Raw | ConvertFrom-Json
    if ([string]$backend.workflow_id -cne 'r011-openintro-statistics-id-b007-backend-stage' -or
        [string]$backend.scope.translated_boundaries[-1] -cne $boundaryId -or
        [string]$backend.stage_state.status -cne 'isolated_final_backend_validated_ready_for_admission' -or
        [string]$backend.final_gates.status -cne 'passed_exact_terminal_inputs_stage_only' -or
        [string]$backend.final_gates.input_manifest.sha256 -cne [string]$boundaryReceipt.final_gate_inputs.sha256 -or
        [string]$backend.final_gates.reviewed_candidate_pdf.sha256 -cne [string]$boundaryReceipt.promoted_pdf.sha256) {
        throw 'Live backend manifest is not the exact byte-promoted admitted B007 stage manifest'
    }
    $backendInventory = Get-TreeInventoryIdentity $backendExportsPath
    if ($backendInventory.file_count -ne [int]$boundaryReceipt.admitted_backend.inventory.file_count -or
        $backendInventory.bytes -ne [int64]$boundaryReceipt.admitted_backend.inventory.bytes -or
        $backendInventory.sha256 -cne [string]$boundaryReceipt.admitted_backend.inventory.sha256) {
        throw 'Live backend inventory differs from the exact B007 admission receipt'
    }
    $identityMap = @($backend.files | Where-Object { $_.path -ceq 'identity_map.jsonl' })
    if ($identityMap.Count -ne 1 -or [int]$identityMap[0].records -ne [int]$boundaryReceipt.admitted_backend.record_count) {
        throw 'Backend identity-map record count is not the exact admitted record count'
    }

    $sourceSelection = Get-SnapshotZipSelection -Root $sourceSnapshot -ManifestPath $snapshotManifestPath -Prefix 'openintro-statistics-id-R011-B007-source' -ExcludedRelativePath $sourceExclusion
    Remove-ExactStagingDirectory -Path $staging -ExpectedParent $releaseParent -ExpectedLeaf $stagingLeaf
    [void](New-Item -ItemType Directory -Path $staging)
    try {
        foreach ($name in $staticMetadataNames) {
            $source = Join-Path $release $name
            $target = Join-Path $staging $name
            Copy-Item -LiteralPath $source -Destination $target
            if ((Get-Sha256 $source) -cne (Get-Sha256 $target)) { throw "Static metadata staging mismatch: $name" }
        }

        $pdfTarget = Join-Path $staging $generatedNames[0]
        Copy-Item -LiteralPath $releasePdfSource -Destination $pdfTarget
        [void](Assert-Identity -Path $pdfTarget -Expected $readerOptimization.optimized_reader -Label 'Staged optimized PDF')

        $sourceZip = Join-Path $staging $generatedNames[1]
        New-DeterministicZip -Path $sourceZip -Items $sourceSelection.Items

        $backendItems = @()
        $backendItems += Get-TreeZipItems -Root $backendExportsPath -Prefix 'backend/exports'
        $backendItems += Get-TreeZipItems -Root (Join-Path $lane 'backend\schemas') -Prefix 'backend/schemas'
        foreach ($name in @('generate_backend_b007.py', 'validate_backend_b007.py', 'admit_b007.py')) {
            $backendItems += New-ZipItem -Source (Join-Path $lane ('scripts\' + $name)) -Entry ('scripts/' + $name)
        }
        $backendItems += New-ZipItem -Source $backendReceiptPath -Entry 'qa/BACKEND_VALIDATION_RECEIPT_R011-B007.json'
        $backendItems += New-ZipItem -Source $finalGateInputsPath -Entry 'qa/R011-B007_FINAL_GATE_INPUTS.json'
        $backendItems += New-ZipItem -Source $boundaryReceiptPath -Entry 'qa/R011-B007_BOUNDARY_RECEIPT.json'
        $backendItems += New-ZipItem -Source $readerOptimizationReceiptPath -Entry 'qa/READER_OPTIMIZATION_RECEIPT_R011-B007.json'
        $backendZip = Join-Path $staging $generatedNames[2]
        New-DeterministicZip -Path $backendZip -Items $backendItems

        $zipVerification = @(
            Test-ZipExact -Path $sourceZip -Items $sourceSelection.Items
            Test-ZipExact -Path $backendZip -Items $backendItems
        )
        if (@($zipVerification | Where-Object filename -ceq $generatedNames[1])[0].entries -ne $sourceSelection.Items.Count) {
            throw 'Source ZIP did not preserve every admitted snapshot entry except the one authorized exclusion'
        }

        $pdfInfo = & pdfinfo.exe $pdfTarget 2>$null
        $pagesLine = @($pdfInfo | Where-Object { $_ -match '^Pages:\s+(\d+)\s*$' })
        if ($pagesLine.Count -ne 1) { throw 'Unable to determine PDF page count' }
        [int]$pdfPages = [regex]::Match($pagesLine[0], '(\d+)').Groups[1].Value
        if ($pdfPages -ne [int]$boundaryReceipt.promoted_pdf.page_count) { throw 'Staged PDF page count differs from admission receipt' }

        $manifestFileNames = @($generatedNames[0..2] + $staticMetadataNames)
        $artifacts = @(
            foreach ($name in $manifestFileNames) {
                $path = Join-Path $staging $name
                [ordered]@{ filename = $name; bytes = [int64](Get-Item -LiteralPath $path).Length; sha256 = Get-Sha256 $path }
            }
        )
        $manifest = [ordered]@{
            schema = 'interlanguage.release-manifest'
            schema_version = '1.1.0'
            release_id = $releaseId
            boundary_id = $boundaryId
            title = 'Statistika Berbasis Data - Edisi Kerja Bahasa Indonesia (R011-B007: Bab 1 dan Bagian 2.1-2.3)'
            status = 'admitted_partial_preservation_release'
            complete_corpus = $false
            publication_date = '2026-08-23'
            production_model = 'OpenAI Codex gpt-5.6-sol, Ultra'
            authority = [ordered]@{
                repository = 'https://github.com/OpenIntroStat/openintro-statistics'
                commit = 'fee25091fb24e89c36296fd67c48c1fcf7a93b6e'
                tree = 'd61cc601e7d97759ce805900520f784d02a0489e'
            }
            admission = [ordered]@{
                status = [string]$boundaryReceipt.status
                boundary_receipt_bytes = $boundaryIdentity.bytes
                boundary_receipt_sha256 = $boundaryIdentity.sha256
                backend_inventory = $backendInventory
                final_gate_inputs_sha256 = Get-Sha256 $finalGateInputsPath
            }
            admitted_scope = @(
                'derivative front matter',
                'Chapter 1 Sections 1.1-1.4',
                'Chapter 1 review exercises 1.35-1.44 and upstream-public answers',
                'Chapter 2 opener and Sections 2.1-2.3',
                'exercises 2.1-2.26 and upstream-public odd answers'
            )
            next_untranslated_unit = 'Chapter 2 review exercises 2.27-2.34'
            pdf = [ordered]@{
                pages = $pdfPages
                bytes = [int64](Get-Item -LiteralPath $pdfTarget).Length
                sha256 = Get-Sha256 $pdfTarget
                lang = 'id-ID'
                tagged = $false
                untranslated_suffix_present = $true
                transport_optimization = [ordered]@{
                    status = [string]$readerOptimization.status
                    admitted_pdf_bytes = [int64]$readerOptimization.admitted_reader.bytes
                    admitted_pdf_sha256 = [string]$readerOptimization.admitted_reader.sha256
                    receipt_bytes = $readerOptimizationReceiptIdentity.bytes
                    receipt_sha256 = $readerOptimizationReceiptIdentity.sha256
                    extracted_text_identical = ([string]$readerOptimization.semantic_and_structure_checks.pdftotext_sha256_source -ceq [string]$readerOptimization.semantic_and_structure_checks.pdftotext_sha256_optimized)
                    rendered_pixels_identical = [bool]$readerOptimization.visual_replay.all_pixels_identical
                }
            }
            backend = [ordered]@{
                boundary_id = $boundaryId
                typed_records = [int]$identityMap[0].records
                manifest_bytes = [int64](Get-Item -LiteralPath $backendManifestPath).Length
                manifest_sha256 = Get-Sha256 $backendManifestPath
                validator_receipt_sha256 = Get-Sha256 $backendReceiptPath
            }
            source_publication_exclusion = [ordered]@{
                status = 'passed_exactly_one_exclusion_all_other_snapshot_entries_preserved'
                relative_path = $sourceExclusion
                bytes = [int64]$sourceSelection.Excluded.Bytes
                sha256 = [string]$sourceSelection.Excluded.Sha256
                admitted_snapshot_entries = [int]$sourceSelection.SnapshotEntries
                packaged_source_entries = [int]$sourceSelection.Items.Count
                excluded_entry_count = 1
            }
            package_verification = $zipVerification
            files = $artifacts
            limitations = @(
                'Chapter 2 review exercise 2.27 onward remains upstream English in the whole-book working-boundary PDF.',
                'The PDF declares id-ID but is not structurally tagged.',
                'The corpus remains in production; this release must not be represented as complete.'
            )
        }
        $manifestPath = Join-Path $staging 'RELEASE_MANIFEST.json'
        [System.IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 12) + "`n", $utf8NoBom)

        $checksumNames = @(Get-OrdinalSortedStrings ($expectedReleaseNames | Where-Object { $_ -cne 'SHA256SUMS.txt' }))
        $checksumLines = @(foreach ($name in $checksumNames) { (Get-Sha256 (Join-Path $staging $name)) + '  ' + $name })
        $checksumsPath = Join-Path $staging 'SHA256SUMS.txt'
        [System.IO.File]::WriteAllLines($checksumsPath, $checksumLines, $utf8NoBom)

        Assert-ExactNames -Actual @(Get-ChildItem -LiteralPath $staging -File -Force | ForEach-Object Name) -Expected $expectedReleaseNames -Label 'Staged nine-file release'
        foreach ($line in Get-Content -LiteralPath $checksumsPath) {
            if ($line -notmatch '^([0-9a-f]{64})  ([^/\\]+)$') { throw "Invalid checksum line: $line" }
            if ((Get-Sha256 (Join-Path $staging $Matches[2])) -cne $Matches[1]) { throw "Checksum readback failed: $($Matches[2])" }
        }
        [int64]$stagedTotalBytes = (Get-ChildItem -LiteralPath $staging -File -Force | Measure-Object Length -Sum).Sum
        if ($stagedTotalBytes -gt $maximumReleaseBytes) { throw "Release payload exceeds $maximumReleaseBytes bytes: $stagedTotalBytes" }

        foreach ($name in $staticMetadataNames) {
            if ((Get-Sha256 (Join-Path $release $name)) -cne (Get-Sha256 (Join-Path $staging $name))) {
                throw "Static metadata changed during packaging: $name"
            }
        }
        foreach ($name in $generatedNames) {
            Move-Item -LiteralPath (Join-Path $staging $name) -Destination (Join-Path $release $name) -Force
        }

        Assert-ExactNames -Actual @(Get-ChildItem -LiteralPath $release -File -Force | ForEach-Object Name) -Expected $expectedReleaseNames -Label 'Final nine-file release'
        $releaseFiles = @(
            foreach ($name in @(Get-OrdinalSortedStrings $expectedReleaseNames)) {
                $path = Join-Path $release $name
                [ordered]@{ filename = $name; bytes = [int64](Get-Item -LiteralPath $path).Length; sha256 = Get-Sha256 $path }
            }
        )
        [int64]$totalBytes = ($releaseFiles | ForEach-Object { [int64]$_.bytes } | Measure-Object -Sum).Sum
        if ($totalBytes -ne $stagedTotalBytes -or $totalBytes -gt $maximumReleaseBytes) { throw 'Final release total differs from the validated staged total or exceeds the cap' }

        $packageReceipt = [ordered]@{
            schema = 'interlanguage.zenodo-package-receipt'
            schema_version = '1.0.0'
            status = 'packaged_exact_nine_files_and_verified'
            release_id = $releaseId
            boundary_id = $boundaryId
            recorded_at = '2026-08-23T00:00:00Z'
            maximum_release_bytes = $maximumReleaseBytes
            total_bytes = $totalBytes
            admission = [ordered]@{
                boundary_receipt = [ordered]@{ bytes = $boundaryIdentity.bytes; sha256 = $boundaryIdentity.sha256 }
                backend_validation_receipt = [ordered]@{ bytes = [int64](Get-Item $backendReceiptPath).Length; sha256 = Get-Sha256 $backendReceiptPath }
                final_gate_inputs = [ordered]@{ bytes = [int64](Get-Item $finalGateInputsPath).Length; sha256 = Get-Sha256 $finalGateInputsPath }
                promoted_pdf = [ordered]@{ bytes = [int64](Get-Item $admittedPdfSource).Length; sha256 = Get-Sha256 $admittedPdfSource }
                public_reader = [ordered]@{ bytes = [int64](Get-Item $releasePdfSource).Length; sha256 = Get-Sha256 $releasePdfSource }
                reader_optimization_receipt = [ordered]@{ bytes = $readerOptimizationReceiptIdentity.bytes; sha256 = $readerOptimizationReceiptIdentity.sha256 }
                backend_inventory = $backendInventory
            }
            source_publication_exclusion = $manifest.source_publication_exclusion
            zip_verification = $zipVerification
            files = $releaseFiles
            credentials_present = $false
        }
        Write-AtomicUtf8Json -Path $packageReceiptPath -Value $packageReceipt
        $receiptReadback = Get-Content -LiteralPath $packageReceiptPath -Raw | ConvertFrom-Json
        if ([string]$receiptReadback.status -cne 'packaged_exact_nine_files_and_verified' -or @($receiptReadback.files).Count -ne 9) {
            throw 'Sanitized package receipt readback failed'
        }

        [pscustomobject]@{
            status = $packageReceipt.status
            release_directory = $release
            total_bytes = $totalBytes
            files = $releaseFiles
            package_receipt_path = $packageReceiptPath
            package_receipt_sha256 = Get-Sha256 $packageReceiptPath
            zip_verification = $zipVerification
        } | ConvertTo-Json -Depth 10
    } finally {
        Remove-ExactStagingDirectory -Path $staging -ExpectedParent $releaseParent -ExpectedLeaf $stagingLeaf
    }
} finally {
    $lockStream.Dispose()
    if (Test-Path -LiteralPath $transactionLockPath) { Remove-Item -LiteralPath $transactionLockPath -Force }
}
