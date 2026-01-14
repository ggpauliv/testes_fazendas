# Deploy Script for AgroTalhoes (Windows -> VPS via PuTTY)
# Requisitos: plink.exe e pscp.exe no PATH, ou na mesma pasta.

$ServerIP = "191.252.178.97"
$RemoteDir = "/home/gestor/site"

Write-Host "=== INICIANDO DEPLOY VIA PUTTY (FIXED) ===" -ForegroundColor Green

# 1. Criar Zip do Projeto (Incluindo migrações e novos arquivos)
Write-Host "[1/3] Compactando arquivos..." -ForegroundColor Cyan
if (Test-Path deploy.zip) { Remove-Item deploy.zip }

# Lista de pastas e arquivos essenciais
$Include = @("core", "agrotalhoes", "templates", "static", "requirements.txt", "manage.py", "deploy_vps.sh", ".env")
Compress-Archive -Path $Include -DestinationPath deploy.zip -Force

# 2. Enviar Scripts e Zip
Write-Host "[2/3] Enviando arquivos para o servidor..." -ForegroundColor Cyan
# Se o usuário não passou senha, o pscp/plink vai tentar usar chaves ou pedir interativamente (se possível)
pscp deploy_vps.sh root@${ServerIP}:${RemoteDir}/deploy_vps.sh
pscp deploy.zip root@${ServerIP}:${RemoteDir}/deploy.zip

# 3. Executar o Deploy no Servidor
Write-Host "[3/3] Executando script de deploy no servidor..." -ForegroundColor Cyan
plink root@${ServerIP} "cd ${RemoteDir} && bash deploy_vps.sh"

Write-Host "=== DEPLOY CONCLUÍDO! ===" -ForegroundColor Green
Write-Host "Acesse: https://hkfazendas.com" -ForegroundColor Yellow
