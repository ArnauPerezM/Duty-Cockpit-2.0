@echo off
title E2Open Duty Optimizer - Build Portable EXE

echo.
echo  =====================================================
echo   E2Open Duty Optimizer  -  Build Portable EXE
echo  =====================================================
echo.
echo  Build output -^> C:\Temp\DutyOptimizer\
echo  (outside OneDrive to avoid file-lock errors)
echo.
echo  Press any key to start, or Ctrl+C to cancel.
pause >nul

echo.
echo [1/3] Installing / updating PyInstaller...
pip install pyinstaller --quiet --upgrade
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Building bundle (this will take a few minutes)...
echo.

pyinstaller ^
  -y ^
  --onedir ^
  --noconsole ^
  --name DutyOptimizer ^
  --noupx ^
  --distpath "C:\Temp\DutyOptimizer_dist" ^
  --workpath "C:\Temp\DutyOptimizer_work" ^
  --collect-all streamlit ^
  --collect-all plotly ^
  --collect-all pycountry ^
  --collect-all openpyxl ^
  --collect-all pandas ^
  --collect-all requests ^
  --copy-metadata streamlit ^
  --copy-metadata requests ^
  --hidden-import streamlit ^
  --hidden-import streamlit.web.cli ^
  --hidden-import streamlit.web.bootstrap ^
  --hidden-import streamlit.runtime ^
  --hidden-import streamlit.runtime.scriptrunner ^
  --hidden-import streamlit.runtime.uploaded_file_manager ^
  --hidden-import streamlit.components.v1 ^
  --hidden-import pandas ^
  --hidden-import openpyxl ^
  --hidden-import openpyxl.styles ^
  --hidden-import pycountry ^
  --hidden-import plotly ^
  --hidden-import plotly.express ^
  --hidden-import requests ^
  --hidden-import sqlite3 ^
  --hidden-import E2Open ^
  --add-data "app.py;." ^
  --add-data "src;src" ^
  --add-data "E2Open.py;." ^
  --add-data ".streamlit;.streamlit" ^
  launcher.py

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed. Review the output above.
    pause
    exit /b 1
)

echo.
echo [3/3] Done!
echo.
echo  =====================================================
echo   Output : C:\Temp\DutyOptimizer_dist\DutyOptimizer\
echo  =====================================================
echo.
echo  Copia la carpeta DutyOptimizer al destino que quieras.
echo  Los usuarios hacen doble-click en DutyOptimizer.exe
echo.
pause
