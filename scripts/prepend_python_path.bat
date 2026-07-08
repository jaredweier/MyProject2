@echo off
REM Prepend Local Python dirs so START HERE.bat works when user PATH is stale.
set "PYROOT=%LOCALAPPDATA%\Python"
if exist "%PYROOT%\bin" set "PATH=%PYROOT%\bin;%PATH%"
for /f "delims=" %%D in ('dir /b /ad "%PYROOT%\pythoncore-*" 2^>nul') do (
    set "PATH=%PYROOT%\%%D;%PYROOT%\%%D\Scripts;%PATH%"
    goto :done
)
:done
exit /b 0
