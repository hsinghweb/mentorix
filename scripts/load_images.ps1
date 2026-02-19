if (!(Test-Path artifacts/mentorix-api.tar)) {
  Write-Error "Missing artifacts/mentorix-api.tar"
  exit 1
}
if (!(Test-Path artifacts/mentorix-postgres.tar)) {
  Write-Error "Missing artifacts/mentorix-postgres.tar"
  exit 1
}
if (!(Test-Path artifacts/mentorix-redis.tar)) {
  Write-Error "Missing artifacts/mentorix-redis.tar"
  exit 1
}

Write-Host "Loading Docker images..."
docker load -i artifacts/mentorix-api.tar
docker load -i artifacts/mentorix-postgres.tar
docker load -i artifacts/mentorix-redis.tar

Write-Host "Done. Run: docker compose up -d"
