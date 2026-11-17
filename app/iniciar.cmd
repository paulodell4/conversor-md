@echo off
REM Conversor MD - iniciado no login do Windows (e pelo menu "Verificar atualizacoes").
REM 1) aplica atualizacao pendente do Python (antes de ele estar em uso)
REM 2) verificacao semanal de atualizacoes
REM 3) abre o icone na bandeja
setlocal
title Conversor MD
set "BASE=%LOCALAPPDATA%\ConversorMD"
if not exist "%BASE%\python.txt" (
    echo Conversor MD nao instalado corretamente. Rode o instalador novamente.
    timeout /t 10 >nul
    exit /b 1
)
set /p PY=<"%BASE%\python.txt"
for %%i in ("%PY%") do set "PYDIR=%%~dpi"
set "PYW=%PYDIR%pythonw.exe"
if not exist "%PYW%" set "PYW=%PY%"

if /i "%~1"=="--forcar" timeout /t 4 /nobreak >nul

if exist "%BASE%\atualizar_python.txt" call :ATUALIZAR_PYTHON

echo Verificando atualizacoes do Conversor MD...
"%PY%" "%BASE%\app\instalador.py" --rotina %1

start "" "%PYW%" "%BASE%\app\bandeja.py"
exit /b 0

:ATUALIZAR_PYTHON
set /p PYNOVA=<"%BASE%\atualizar_python.txt"
del /q "%BASE%\atualizar_python.txt" >nul 2>&1
echo Atualizando o Python para %PYNOVA%...
set "PYEXE=%TEMP%\python-%PYNOVA%-amd64.exe"
curl.exe -L --fail -s -o "%PYEXE%" "https://www.python.org/ftp/python/%PYNOVA%/python-%PYNOVA%-amd64.exe"
if errorlevel 1 exit /b 0
"%PYEXE%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=0 Shortcuts=0
del /q "%PYEXE%" >nul 2>&1
exit /b 0
