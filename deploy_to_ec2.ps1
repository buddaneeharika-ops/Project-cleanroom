# One-click deployment script to EC2
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Deploying to EC2 (3.109.60.230)..." -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$KeyFile = "cms-cron-operations.pem"

if (-not (Test-Path $KeyFile)) {
    Write-Host "[ERROR] $KeyFile not found in current directory!" -ForegroundColor Red
    exit 1
}

$RemoteCommand = @"
cd /home/ec2-user/Form20-backlog-tracker && \
git pull origin main && \
redis6-cli flushall && \
./venv/bin/python3 -c 'import cron_daily_state_glance; cron_daily_state_glance.sync_json_to_redis()' && \
sudo systemctl restart form20-dashboard.service && \
echo '>>> DEPLOYMENT_SUCCESSFUL <<<'
"@

ssh.exe -o StrictHostKeyChecking=no -i $KeyFile ec2-user@3.109.60.230 $RemoteCommand

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[SUCCESS] Production deployment complete!" -ForegroundColor Green
    Write-Host "Live Domain: https://proj-cleanroom.duckdns.org/dashboard" -ForegroundColor Green
} else {
    Write-Host "`n[ERROR] Deployment failed with exit code $LASTEXITCODE" -ForegroundColor Red
}
