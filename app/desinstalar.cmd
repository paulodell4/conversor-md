@echo off
REM Remove o Conversor MD. Mantem a pasta da Area de Trabalho, o Python e o OpenWhispr.
setlocal
if /i not "%~1"=="--temp" (
    copy /y "%~f0" "%TEMP%\desinstalar_conversor_md.cmd" >nul
    start "Desinstalar Conversor MD" "%TEMP%\desinstalar_conversor_md.cmd" --temp
    exit /b 0
)
title Desinstalar Conversor MD
echo.
echo  Isto remove o Conversor MD deste computador.
echo  A pasta "Conversor MD" da Area de Trabalho e seus arquivos serao MANTIDOS.
echo  O Python e o OpenWhispr tambem serao mantidos.
echo.
choice /M "  Deseja continuar"
if errorlevel 2 exit /b 0

set "BASE=%LOCALAPPDATA%\ConversorMD"
if exist "%BASE%\pid.txt" (
    set /p PIDANT=<"%BASE%\pid.txt"
    call taskkill /pid %%PIDANT%% /f >nul 2>&1
)
timeout /t 2 /nobreak >nul
set "PROGS=%APPDATA%\Microsoft\Windows\Start Menu\Programs"
del /q "%PROGS%\Startup\Conversor MD.lnk" >nul 2>&1
del /q "%PROGS%\Startup\Conversor MD.bat" >nul 2>&1
rmdir /s /q "%PROGS%\Conversor MD" >nul 2>&1
rmdir /s /q "%BASE%" >nul 2>&1
echo.
echo  Conversor MD removido.
echo.
pause
