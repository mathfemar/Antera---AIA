@echo off
echo ================================
echo   Criando nova versão no GitHub
echo ================================
echo.

:: Garante que o diretório atual seja o mesmo do .bat
cd /d %~dp0

:: Solicita a versão ao usuário
set /p versionNumber=Digite o número da nova versão (ex.: 1.0.3): 

echo.
echo Versão digitada: %versionNumber%
echo.

:: Executa os comandos do Git
git add .
git commit -m "Nova versão: %versionNumber%"
git pull --rebase origin main
git push origin main

echo.
echo Pressione qualquer tecla para sair...
pause > nul
