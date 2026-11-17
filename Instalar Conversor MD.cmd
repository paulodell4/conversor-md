@echo off
REM ============================================================
REM  Conversor MD - instalador (Baraldi Advocacia)
REM  De dois cliques neste arquivo. Ele instala ou atualiza tudo:
REM  Python, Conversor MD, Node.js, OpenWhispr e componentes.
REM ============================================================
setlocal
chcp 65001 >nul
title Instalador - Conversor MD
set "REPO=paulodell4/conversor-md"
set "PYVER=3.13.17"
set "BASE=%LOCALAPPDATA%\ConversorMD"
set "PY="

echo.
echo  ==============================================
echo     CONVERSOR MD - instalacao
echo  ==============================================
echo.

REM ---------- 0. encerra versao anterior, se estiver rodando
if exist "%BASE%\pid.txt" (
    set /p PIDANT=<"%BASE%\pid.txt"
    call taskkill /pid %%PIDANT%% /f >nul 2>&1
)

REM ---------- 1. Python
echo  [1/3] Verificando o Python...
if exist "%BASE%\atualizar_python.txt" call :ATUALIZAR_PYTHON_PENDENTE
call :ACHAR_PYTHON
if defined PY goto PYTHON_OK

echo        Python nao encontrado. Baixando Python %PYVER% ...
set "PYEXE=%TEMP%\python-%PYVER%-amd64.exe"
curl.exe -L --fail -# -o "%PYEXE%" "https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-amd64.exe"
if errorlevel 1 goto ERRO_DOWNLOAD
echo        Instalando Python (cerca de 1 minuto)...
"%PYEXE%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=0 Shortcuts=0
del /q "%PYEXE%" >nul 2>&1
set "PYNOSSO=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not exist "%PYNOSSO%" goto ERRO_PYTHON
set "PY=%PYNOSSO%"
if not exist "%BASE%" mkdir "%BASE%"
echo nosso> "%BASE%\python_nosso.txt"

:PYTHON_OK
echo        Python: %PY%

REM ---------- 2. arquivos do Conversor MD
echo  [2/3] Baixando o Conversor MD...
if not exist "%BASE%\app" mkdir "%BASE%\app"
if exist "%~dp0app\instalador.py" (
    echo        usando os arquivos desta pasta
    xcopy /e /i /y /q "%~dp0app" "%BASE%\app" >nul
    copy /y "%~dp0VERSION" "%BASE%\app\VERSION" >nul
    goto ARQUIVOS_OK
)
set "TMPZIP=%TEMP%\conversor-md.zip"
set "TMPDIR=%TEMP%\conversor-md-extraido"
if exist "%TMPDIR%" rmdir /s /q "%TMPDIR%"
mkdir "%TMPDIR%"
curl.exe -L --fail -s -o "%TMPZIP%" "https://github.com/%REPO%/archive/refs/heads/main.zip"
if errorlevel 1 goto ERRO_DOWNLOAD
tar -xf "%TMPZIP%" -C "%TMPDIR%"
if errorlevel 1 goto ERRO_DOWNLOAD
for /d %%d in ("%TMPDIR%\*") do (
    xcopy /e /i /y /q "%%d\app" "%BASE%\app" >nul
    copy /y "%%d\VERSION" "%BASE%\app\VERSION" >nul
)
del /q "%TMPZIP%" >nul 2>&1
rmdir /s /q "%TMPDIR%" >nul 2>&1

:ARQUIVOS_OK
if not exist "%BASE%\app\instalador.py" goto ERRO_DOWNLOAD

REM ---------- 3. janela de instalacao (faz o resto)
echo  [3/3] Abrindo a janela de instalacao. Acompanhe por ela.
for %%i in ("%PY%") do set "PYW=%%~dpipythonw.exe"
if not exist "%PYW%" set "PYW=%PY%"
start "" /wait "%PYW%" "%BASE%\app\instalador.py"
exit /b 0

REM ============================================================
:ACHAR_PYTHON
REM Prioridade: Python instalado pelo Conversor MD > py launcher > python no PATH
set "PY="
if exist "%BASE%\python.txt" (
    set /p PY=<"%BASE%\python.txt"
)
if defined PY if exist "%PY%" call :TESTAR_PYTHON "%PY%"
if defined PY exit /b 0
for /f "usebackq delims=" %%i in (`py -3 -c "import sys;print(sys.executable)" 2^>nul`) do call :TESTAR_PYTHON "%%i"
if defined PY exit /b 0
for /f "usebackq delims=" %%i in (`python -c "import sys;print(sys.executable)" 2^>nul`) do call :TESTAR_PYTHON "%%i"
exit /b 0

:TESTAR_PYTHON
REM aceita somente Python 3.10 ou mais novo
set "PY="
if not exist "%~1" exit /b 0
"%~1" -c "import sys;sys.exit(sys.hexversion<0x30A0000)" >nul 2>&1
if errorlevel 1 exit /b 0
set "PY=%~1"
exit /b 0

:ATUALIZAR_PYTHON_PENDENTE
set /p PYNOVA=<"%BASE%\atualizar_python.txt"
del /q "%BASE%\atualizar_python.txt" >nul 2>&1
echo        Atualizando o Python para %PYNOVA% ...
set "PYUP=%TEMP%\python-%PYNOVA%-amd64.exe"
curl.exe -L --fail -s -o "%PYUP%" "https://www.python.org/ftp/python/%PYNOVA%/python-%PYNOVA%-amd64.exe"
if errorlevel 1 exit /b 0
"%PYUP%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=0 Shortcuts=0
del /q "%PYUP%" >nul 2>&1
exit /b 0

:ERRO_DOWNLOAD
echo.
echo  [ERRO] Nao foi possivel baixar os arquivos. Verifique a internet
echo  ou se a rede do escritorio bloqueia github.com / python.org.
echo.
pause
exit /b 1

:ERRO_PYTHON
echo.
echo  [ERRO] O Python nao foi instalado. A TI pode estar bloqueando instalacoes.
echo  Peca a TI para instalar o Python 3.13 e rode este arquivo de novo.
echo.
pause
exit /b 1
