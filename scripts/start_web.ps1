# Start Ghost-User Next.js Dashboard
$ErrorActionPreference = "Stop"

Write-Host "Starting Ghost-User Dashboard on http://localhost:3000..." -ForegroundColor Cyan
npm run dev --workspace=apps/web
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
