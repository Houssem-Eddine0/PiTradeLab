# Cross-build de l'image Pi Zero (ARMv6) SUR PC, export en fichier .tar.
# Prérequis : Docker Desktop (WSL2). Lancer depuis le dossier du projet :
#   powershell -ExecutionPolicy Bypass -File build-pi.ps1
$ErrorActionPreference = "Stop"

Write-Host "==> 1/4 Activation de l'emulation ARM (QEMU/binfmt)..." -ForegroundColor Cyan
docker run --privileged --rm tonistiigi/binfmt --install arm | Out-Null

Write-Host "==> 2/4 Preparation du builder buildx..." -ForegroundColor Cyan
docker buildx create --name pizero --driver docker-container --use 2>$null | Out-Null
docker buildx use pizero
docker buildx inspect --bootstrap | Out-Null

Write-Host "==> 3/4 Build ARMv6 (emulation lente, patiente ~5-15 min)..." -ForegroundColor Cyan
docker buildx build --platform linux/arm/v6 `
    -f Dockerfile.pi `
    -t pitradelab:pi `
    --output type=docker,dest=pitradelab-pi.tar .

Write-Host "==> 4/4 Termine. Image exportee : pitradelab-pi.tar" -ForegroundColor Green
Write-Host ""
Write-Host "Sur le Pi Zero :" -ForegroundColor Yellow
Write-Host "  scp pitradelab-pi.tar docker-compose.pi.yml .env  pi@<IP_DU_PI>:~/pitradelab/"
Write-Host "  ssh pi@<IP_DU_PI>"
Write-Host "  cd ~/pitradelab && docker load -i pitradelab-pi.tar"
Write-Host "  docker compose -f docker-compose.pi.yml up -d"
