New-Item -ItemType Directory -Force artifacts | Out-Null

Write-Host "Building latest images from compose..."
docker compose build

Write-Host "Exporting images to artifacts/*.tar ..."
docker save mentorix-api:latest -o artifacts/mentorix-api.tar
docker save pgvector/pgvector:pg16 -o artifacts/mentorix-postgres.tar
docker save redis:7-alpine -o artifacts/mentorix-redis.tar

Write-Host "Done. Share the 'artifacts' folder and project files."
