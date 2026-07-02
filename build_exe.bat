@echo off
title Duty Optimizer - Build Portable EXE

echo.
echo  =====================================================
echo   Duty Optimizer  -  Build Portable EXE
echo  =====================================================
echo.
echo  Build output -^> C:\Temp\DutyOptimizer_dist\DutyOptimizer\
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
echo [2/3] Building bundle from DutyOptimizer.spec (this will take a few minutes)...
echo.

pyinstaller -y ^
  --distpath "C:\Temp\DutyOptimizer_dist" ^
  --workpath "C:\Temp\DutyOptimizer_work" ^
  DutyOptimizer.spec

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
