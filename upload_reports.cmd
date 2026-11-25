@echo off
chcp 65001 >nul
setlocal
cd /d D:\models

rem Use the interpreter that is known to have boto3; fall back to PATH python.
set PY="C:\Users\1\.workbuddy-ai\binaries\python\versions\3.13.12\python.exe"
if not exist %PY% set PY=python

echo ================================================
echo  Uploading VDO reports to S3 (bucket rsbu)
echo  Storage class: STANDARD (задан в publish_reports.py, не флагом)
echo  Interpreter: %PY%
echo ================================================
echo.

echo [1/2] 9 months 2026
%PY% publish_reports.py --period 9m --year 2026
if errorlevel 1 echo *** 2026 finished with errors, see output above

echo.
echo [2/2] 9 months 2025
%PY% publish_reports.py --period 9m --year 2025
if errorlevel 1 echo *** 2025 finished with errors, see output above

echo.
echo Done. Link tables:
echo   _links_9m_2026.csv
echo   _links_9m_2025.csv
echo.
pause
