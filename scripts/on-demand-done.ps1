# Stop hook (ADR 0021): when an on-demand Claude session finishes its turn, tell the backend, which
# then closes its window. Every other session has no ARCHEION_ON_DEMAND_DONE and returns at once.
$marker = $env:ARCHEION_ON_DEMAND_DONE
if (-not $marker) { exit 0 }
try {
    Set-Content -LiteralPath $marker -Value (Get-Date -Format o) -Encoding ascii
} catch {
    # The backend falls back to the process exiting; never block the session over this.
}
exit 0
