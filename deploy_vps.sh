#!/bin/bash

# Script de Atualização (Deploy) - AgroTalhoes v3.02 (FIXED)
# Executar este script dentro da pasta do projeto na VPS.

PROJECT_DIR="/home/gestor/site" 
VENV_PATH="$PROJECT_DIR/venv"
LOG_FILE="$PROJECT_DIR/logs/deploy_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$PROJECT_DIR/logs"

echo "--- Iniciando Atualização v3.02 ---" | tee -a "$LOG_FILE"

# 1. Ajuste de Ambiente (Evita erro de OpenSSL no pip)
export CRYPTOGRAPHY_OPENSSL_NO_LEGACY=1

# 2. Puxar código novo
if [ -f "$PROJECT_DIR/deploy.zip" ]; then
    echo "2. Detectado deploy.zip. Extraindo..." | tee -a "$LOG_FILE"
    unzip -o "$PROJECT_DIR/deploy.zip" -d "$PROJECT_DIR"
    rm "$PROJECT_DIR/deploy.zip"
else
    echo "2. Atualizando código via Git..." | tee -a "$LOG_FILE"
    # Garante que estamos na branch correta e puxa as novidades
    git checkout main
    git pull origin main
    git reset --hard origin/main
fi

# 3. Ativar Venv e Instalar dependências
echo "3. Verificando dependências..." | tee -a "$LOG_FILE"
if [ ! -d "$VENV_PATH" ]; then
    echo "Criando novo ambiente virtual..."
    python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"

# Upgrade pip primeiro para evitar erros de pacotes antigos
python3 -m pip install --upgrade pip --quiet

echo "Instalando pacotes do requirements.txt..." | tee -a "$LOG_FILE"
pip install -r requirements.txt --quiet | tee -a "$LOG_FILE"

# 4. Rodar Migrações
echo "4. Aplicando mudanças no Banco de Dados..." | tee -a "$LOG_FILE"
python3 manage.py migrate --noinput | tee -a "$LOG_FILE"

# 5. Coletar Estáticos
echo "5. Atualizando arquivos estáticos..." | tee -a "$LOG_FILE"
python3 manage.py collectstatic --noinput | tee -a "$LOG_FILE"

# 6. Reiniciar Gunicorn (Nome correto na sua VPS)
echo "6. Reiniciando Servidor de Aplicação (Gunicorn)..." | tee -a "$LOG_FILE"
sudo systemctl restart gunicorn

# 7. Reiniciar Nginx
echo "7. Reiniciando Nginx..." | tee -a "$LOG_FILE"
sudo systemctl restart nginx

echo "--- Atualização Finalizada com Sucesso! ---" | tee -a "$LOG_FILE"
echo "Acesse https://hkfazendas.com para verificar."
