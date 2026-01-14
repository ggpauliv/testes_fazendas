# Deploy Script for Gestor Talhao (Windows -> Linux)
param(
    [string]$ServerIP = "191.252.178.97"
)

$ErrorActionPreference = "Stop"
Write-Host "=== INICIANDO DEPLOY PARA $ServerIP (FIXED) ===" -ForegroundColor Green

# 1. Criar Zip do Projeto
Write-Host "[1/4] Compactando arquivos..." -ForegroundColor Cyan
if (Test-Path deploy.zip) { Remove-Item deploy.zip }
Compress-Archive -Path core, agrotalhoes, templates, static, requirements.txt, manage.py -DestinationPath deploy.zip -Force

# 2. Enviar para o Servidor
Write-Host "[2/4] Enviando arquivos (Senha Locaweb)..." -ForegroundColor Cyan
scp deploy.zip root@${ServerIP}:/home/gestor/site/deploy.zip

# 3. Executar comandos remotos
Write-Host "[3/4] Configurando no Servidor..." -ForegroundColor Cyan

# Comandos unificados com ; para evitar problemas de quebra de linha do Windows
$RemoteCommands = "
    export DEBIAN_FRONTEND=noninteractive;
    apt-get update && apt-get install -y unzip;
    cd /home/gestor/site;
    rm -rf core agrotalhoes templates static requirements.txt manage.py;
    unzip -o deploy.zip;
    rm deploy.zip;
    chown -R gestor:www-data /home/gestor/site;
    chmod -R 775 /home/gestor/site;
    su - gestor -c 'cd /home/gestor/site && python3 -m venv venv';
    su - gestor -c 'cd /home/gestor/site && source venv/bin/activate && pip install -r requirements.txt';
    su - gestor -c 'cd /home/gestor/site && source venv/bin/activate && python manage.py collectstatic --noinput';
    su - gestor -c 'cd /home/gestor/site && source venv/bin/activate && python manage.py migrate';
    systemctl restart gunicorn;
"

# Remove quebras de linha do Windows que quebram o Linux
$CleanCommands = $RemoteCommands -replace "`r", ""

ssh root@$ServerIP "$CleanCommands"

Write-Host "=== DEPLOY CONCLUÍDO! ===" -ForegroundColor Green
Write-Host "Acesse: http://$ServerIP" -ForegroundColor Yellow
