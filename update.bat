@echo off
cd /d %~dp0

:: Verifica se o diretório atual é um repositório Git
if not exist ".git" (
    echo Repositório Git não encontrado.
    echo Clonando o repositório do GitHub...
    git clone https://github.com/mathfemar/Antera---AIA.git
) else (
    echo Repositório Git encontrado.
    echo Sincronizando com o repositório remoto...
    git fetch --all
    git reset --hard origin/main
    git clean -fd --exclude=send.bat --exclude=*.exe
)

exit
