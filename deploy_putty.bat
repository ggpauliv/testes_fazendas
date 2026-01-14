@echo off
SET SERVER_IP=191.252.178.97
SET REMOTE_DIR=/home/gestor/site

echo === EXECUTANDO DEPLOY REMOTO (VIA PLINK) ===
echo [1/1] Conectando ao servidor e iniciando deploy_vps.sh...

:: Nota: Certifique-se que o plink.exe esta no seu PATH.
:: Recomendado usar o Pageant com sua chave SSH carregada.
plink -pw "SUA_SENHA_AQUI" root@%SERVER_IP% "cd %REMOTE_DIR% && bash deploy_vps.sh"

if %ERRORLEVEL% NEQ 0 (
    echo [ERRO] Falha ao executar comandos remotos.
    pause
    exit /b %ERRORLEVEL%
)

echo Deploy concluido com sucesso!
pause
