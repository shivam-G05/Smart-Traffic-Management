# Converts Word documents to PDF with the installed Microsoft Word, so the
# build output can be checked exactly as a reader (or the conference
# system) will see it.
#   powershell -File paper/to_pdf.ps1 paper/out/a.docx [paper/out/b.docx ...]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Files)

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0  # never wait on a dialog
try {
    foreach ($file in $Files) {
        $full = (Resolve-Path $file).Path
        $pdf = [System.IO.Path]::ChangeExtension($full, ".pdf")
        $doc = $word.Documents.Open($full, $false, $true)
        $doc.SaveAs([ref]$pdf, [ref]17)  # 17 = wdFormatPDF
        $doc.Close([ref]0)
        Write-Output "wrote $pdf"
    }
}
finally {
    $word.Quit([ref]0)  # 0 = wdDoNotSaveChanges (also skips the Normal template prompt)
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
