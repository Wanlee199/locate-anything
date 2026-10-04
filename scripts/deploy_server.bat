@echo off
REM ==============================================================================
REM 🚀 Windows Server / Local Machine Deployment & Auto-Update Script
REM ==============================================================================

setlocal enabledelayedexpansion
set BRANCH=locateV2
cd /d "%~dp0\.."

if "%1"=="" goto help
if "%1"=="--help" goto help
if "%1"=="help" goto help
if "%1"=="--install" goto install
if "%1"=="install" goto install
if "%1"=="--update" goto update
if "%1"=="update" goto update
if "%1"=="--status" goto status
if "%1"=="status" goto status
if "%1"=="--test" goto test
if "%1"=="test" goto test
if "%1"=="--sync" goto sync
if "%1"=="sync" goto sync

:install
echo ======================================================================
echo 🚀 CAI DAT HE THONG TREN WINDOWS (LOCATE-ANYTHING)
echo ======================================================================
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt gdown
python tools/setup_3d_model.py
python -m unittest discover tests
echo [OK] Cai dat hoan tat!
goto end

:update
echo ======================================================================
echo 🔄 CAP NHAT MA NGUON TU GITHUB (NHANH %BRANCH%)
echo ======================================================================
git fetch origin %BRANCH%
git checkout %BRANCH%
git pull origin %BRANCH%
python -m pip install -q -r requirements.txt
python tools/setup_3d_model.py
python -m unittest discover tests
echo [OK] Cap nhat thanh cong!
goto end

:status
echo ======================================================================
echo 🩺 KIEM TRA TRANG THAI LOCATE-ANYTHING
echo ======================================================================
git branch --show-current
git log -1 --oneline
python --version
python -m unittest discover tests
goto end

:test
python -m unittest discover tests
goto end

:sync
shift
python colab/cvat_auto_sync.py %*
goto end

:help
echo Cach su dung scripts\deploy_server.bat:
echo   scripts\deploy_server.bat install     Cai dat dependencies va weights
echo   scripts\deploy_server.bat update      Keo code moi nhat tu Git va cap nhat
echo   scripts\deploy_server.bat status      Kiem tra trang thai he thong
echo   scripts\deploy_server.bat test        Chay bo test suite
echo   scripts\deploy_server.bat sync [args] Chay cvat_auto_sync.py voi tham so
goto end

:end
endlocal
