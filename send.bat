@echo off
echo =================================
echo   Enviando alterações para o GitHub (Force Push)
echo =================================
echo.

:: Garante que o diretório atual seja o mesmo do .bat
cd /d %~dp0

:: Solicita o número da nova versão
set /p versionNumber=Digite o número da nova versão (ex.: 1.0.3): 

echo.
echo Versão digitada: %versionNumber%
echo.

:: Adiciona os arquivos, cria o commit e faz o force push
git add .
git commit -m "Nova versão: %versionNumber%"
git push --force origin main

echo.
echo Alterações enviadas com sucesso.
pause
