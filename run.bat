@echo off
chcp 65001 >nul
echo =======================================
echo    🚀 Primatech Investment Analyzer
echo =======================================

:: Verificar se o Python está instalado
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ⚠️ Python não encontrado. Baixando o instalador...
    curl -o python-installer.exe https://www.python.org/ftp/python/3.10.0/python-3.10.0-amd64.exe
    start /wait python-installer.exe /quiet InstallAllUsers=1 PrependPath=1
    del python-installer.exe
) ELSE (
    echo ✅ Python está instalado.
)

:: Verificar se o Git está instalado
git --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ⚠️ Git não encontrado. Baixando o instalador do Git for Windows...
    curl -o git-installer.exe https://github.com/git-for-windows/git/releases/download/v2.41.0.windows.1/Git-2.41.0-64-bit.exe
    start /wait git-installer.exe /VERYSILENT
    del git-installer.exe
) ELSE (
    echo ✅ Git está instalado.
)

:: Garantir que o PIP está instalado
python -m ensurepip --default-pip >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo ⚠️ Instalando o PIP...
    python -m ensurepip
) ELSE (
    echo ✅ PIP já está instalado.
)

:: Atualizar o PIP
echo 🔄 Atualizando o PIP...
python -m pip install --upgrade pip

:: Instalar dependências do requirements.txt
echo 📦 Instalando dependências do requirements.txt...
pip install -r requirements.txt

:: Limpar o cache do Streamlit
echo 🧹 Limpando cache do Streamlit...
rmdir /s /q "%USERPROFILE%\.streamlit\cache" 2>nul
rmdir /s /q "%USERPROFILE%\.streamlit\runtime" 2>nul

:: Configurar o Streamlit para evitar o prompt de e-mail
mkdir "%USERPROFILE%\.streamlit" >nul 2>&1
echo [server] > "%USERPROFILE%\.streamlit\config.toml"
echo headless = true >> "%USERPROFILE%\.streamlit\config.toml"
echo enableCORS = false >> "%USERPROFILE%\.streamlit\config.toml"
echo browser.gatherUsageStats = false >> "%USERPROFILE%\.streamlit\config.toml"

:: Fechar qualquer instância do Streamlit que possa estar rodando
echo 🔄 Encerrando instâncias anteriores...
taskkill /F /IM "streamlit.exe" 2>nul
taskkill /F /IM "python.exe" /FI "WINDOWTITLE eq streamlit" 2>nul

:: Aguardar um momento para garantir que as portas foram liberadas
timeout /t 2 /nobreak >nul

:: Iniciar o aplicativo com o Streamlit
echo 🚀 Iniciando o Primatech Analyzer...
start "" http://localhost:8504
python -m streamlit run app.py --server.port=8504 --server.headless true

:: Manter o CMD aberto para visualizar erros
pause
