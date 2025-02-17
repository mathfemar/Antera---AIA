@echo off
chcp 65001 >nul

:: Muda para o diretório do script
cd /d %~dp0

:: Verifica se o Python está instalado
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Python nao encontrado. Baixando o instalador do Python...
    curl -o python-installer.exe https://www.python.org/ftp/python/3.10.0/python-3.10.0-amd64.exe
    start /wait python-installer.exe /quiet InstallAllUsers=1 PrependPath=1
    del python-installer.exe
) ELSE (
    echo Python ja esta instalado.
)

:: Verifica se o Git está instalado
git --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Git nao encontrado. Baixando o instalador do Git for Windows...
    curl -o git-installer.exe https://github.com/git-for-windows/git/releases/download/v2.41.0.windows.1/Git-2.41.0-64-bit.exe
    start /wait git-installer.exe /VERYSILENT
    del git-installer.exe
) ELSE (
    echo Git ja esta instalado.
)

:: Verifica se o diretório atual é um repositório Git
if not exist ".git" (
    echo Repositorio Git nao encontrado.
    echo Clonando o repositorio do GitHub...
    git clone https://github.com/mathfemar/Antera---AIA.git .
) else (
    echo Repositorio Git encontrado.
    echo Sincronizando com o repositorio remoto...
    git fetch --all
    git reset --hard origin/main
    git clean -fdx
)

exit
