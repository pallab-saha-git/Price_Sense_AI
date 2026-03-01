@echo off
REM ============================================================
REM  setup.bat — Price Sense AI: One-Click Data Setup (Windows)
REM ============================================================
REM  Downloads dunnhumby datasets, generates synthetic CSVs,
REM  and seeds the SQLite database so app.py is ready to run.
REM
REM  Usage:
REM    setup.bat              — full setup (download + generate + seed)
REM    setup.bat --skip-download  — skip dunnhumby download (synthetic only)
REM    setup.bat --skip-lgsr      — skip the 4.3 GB LGSR dataset
REM    setup.bat --force          — re-download and re-seed even if already done
REM ============================================================

setlocal EnableDelayedExpansion

REM ── Colour codes / header ───────────────────────────────────────────────────
echo.
echo ======================================================
echo   Price Sense AI — Data Setup
echo ======================================================
echo.

REM ── Parse arguments ─────────────────────────────────────────────────────────
set "SKIP_DOWNLOAD=0"
set "SKIP_LGSR=0"
set "SKIP_CJ=0"
set "FORCE=0"

:parse_args
if "%~1"=="" goto :done_args
if /I "%~1"=="--skip-download" set "SKIP_DOWNLOAD=1"
if /I "%~1"=="--skip-lgsr"    set "SKIP_LGSR=1"
if /I "%~1"=="--skip-cj"      set "SKIP_CJ=1"
if /I "%~1"=="--force"        set "FORCE=1"
shift
goto :parse_args
:done_args

REM ── Locate project root (same folder as this .bat) ─────────────────────────
cd /d "%~dp0"
set "PROJECT_ROOT=%CD%"
echo [info] Project root: %PROJECT_ROOT%
echo.

REM ── Check Python is available ───────────────────────────────────────────────
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not found on PATH.
    echo         Please install Python 3.10+ from https://www.python.org/downloads/
    echo         and make sure "Add Python to PATH" is checked during installation.
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
echo [info] Found: %PY_VER%

REM ── Create required directories ─────────────────────────────────────────────
echo.
echo [Step 1/6] Creating directories ...
if not exist "data\zip"        mkdir "data\zip"
if not exist "data\raw"        mkdir "data\raw"
if not exist "data\synthetic"  mkdir "data\synthetic"
if not exist "data\processed"  mkdir "data\processed"
if not exist "logs"            mkdir "logs"
echo           Done.

REM ── Install / upgrade Python dependencies ──────────────────────────────────
echo.
echo [Step 2/6] Installing Python dependencies from requirements.txt ...
echo           (this may take a few minutes on first run)
echo.
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] pip install failed. Check the output above for details.
    echo         You may need to install Microsoft Visual C++ Build Tools for
    echo         packages like Prophet / statsmodels:
    echo         https://visualstudio.microsoft.com/visual-cpp-build-tools/
    exit /b 1
)
echo.
echo           Dependencies installed successfully.

REM ── Download dunnhumby datasets ─────────────────────────────────────────────
echo.
echo [Step 3/6] Downloading dunnhumby datasets ...

if "%SKIP_DOWNLOAD%"=="1" (
    echo           --skip-download flag set — skipping all downloads.
    goto :after_download
)

REM Pass environment variables to the Python downloader
set "SKIP_LGSR_ENV="
set "SKIP_CJ_ENV="
if "%SKIP_LGSR%"=="1" set "SKIP_LGSR_ENV=SKIP_LGSR=1"
if "%SKIP_CJ%"=="1"   set "SKIP_CJ_ENV=SKIP_CJ=1"

REM Check if datasets already present (unless --force)
if "%FORCE%"=="0" (
    if exist "data\zip\dunnhumby_The-Complete-Journey.zip" (
        echo           dunnhumby_The-Complete-Journey.zip already exists.
        set "SKIP_CJ_ENV=SKIP_CJ=1"
    )
)

echo.
echo           Downloading from dunnhumby.com (direct public links).
echo           The Complete Journey : ~128 MB
echo           LGSR 9-part set     : ~4.3 GB total (skip with --skip-lgsr)
echo.
echo           Downloads are resumable — you can re-run setup.bat if interrupted.
echo.

if defined SKIP_LGSR_ENV ( set "%SKIP_LGSR_ENV%" )
if defined SKIP_CJ_ENV   ( set "%SKIP_CJ_ENV%" )

if "%FORCE%"=="1" (
    python data\download_dunnhumby.py --force
) else (
    python data\download_dunnhumby.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [WARNING] Some downloads may have failed. The app will still work
    echo           with synthetic data. You can re-run setup.bat to retry.
)

:after_download

REM ── Generate synthetic CSV data ─────────────────────────────────────────────
echo.
echo [Step 4/6] Generating synthetic demo data CSVs ...

set "SYNTH_EXISTS=0"
if exist "data\synthetic\products.csv" if exist "data\synthetic\sales.csv" if exist "data\synthetic\stores.csv" set "SYNTH_EXISTS=1"

if "%SYNTH_EXISTS%"=="1" if "%FORCE%"=="0" (
    echo           Synthetic CSVs already exist — skipping. Use --force to regenerate.
    goto :after_synthetic
)

python data\synthetic_generator.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Synthetic data generation failed.
    exit /b 1
)
echo           Synthetic CSVs generated in data\synthetic\

:after_synthetic

REM ── Verify CSV files ────────────────────────────────────────────────────────
echo.
echo [Step 5/6] Verifying data files ...
echo.

set "MISSING=0"
set "CSV_LIST=products stores sales promotions calendar_events competitor_events customer_segments seasonality_index weather_index"

for %%f in (%CSV_LIST%) do (
    if exist "data\synthetic\%%f.csv" (
        echo           [OK]   data\synthetic\%%f.csv
    ) else (
        echo           [MISS] data\synthetic\%%f.csv
        set "MISSING=1"
    )
)

echo.

REM Check for dunnhumby zips
if exist "data\zip\dunnhumby_The-Complete-Journey.zip" (
    echo           [OK]   data\zip\dunnhumby_The-Complete-Journey.zip
) else (
    echo           [----] data\zip\dunnhumby_The-Complete-Journey.zip  (optional)
)

set "LGSR_COUNT=0"
for /L %%n in (1,1,9) do (
    REM Check both apostrophe variants
    if exist "data\zip\dunnhumby_Let*Sort-of-Real*Part-%%n-of-9*.zip" (
        set /A LGSR_COUNT+=1
    )
)
echo           [info] LGSR zip parts found: %LGSR_COUNT% / 9  (optional)

if "%MISSING%"=="1" (
    echo.
    echo [WARNING] Some required CSV files are missing.
    echo           Try running:  python data\synthetic_generator.py
)

REM ── Seed database ───────────────────────────────────────────────────────────
echo.
echo [Step 6/6] Seeding SQLite database ...

if "%FORCE%"=="1" (
    python -c "from data.seed_data import seed_database; seed_database(force=True)"
) else (
    python -c "from data.seed_data import seed_database; seed_database(force=False)"
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Database seeding failed. Check the output above.
    exit /b 1
)

REM ── Optionally load dunnhumby data into the database ────────────────────────
if exist "data\zip\dunnhumby_The-Complete-Journey.zip" (
    echo.
    echo [Bonus] Loading dunnhumby real data into database ...
    if "%FORCE%"=="1" (
        python -c "from data.load_dunnhumby import load_dunnhumby; load_dunnhumby(force=True)"
    ) else (
        python -c "from data.load_dunnhumby import load_dunnhumby; load_dunnhumby(force=False)"
    )
    if %ERRORLEVEL% NEQ 0 (
        echo [WARNING] Dunnhumby ingestion had errors — synthetic data is still usable.
    ) else (
        echo           Dunnhumby data loaded successfully.
    )
)

REM ── Done ────────────────────────────────────────────────────────────────────
echo.
echo ======================================================
echo   Setup Complete!
echo ======================================================
echo.
echo   To start the app, run:
echo.
echo       python app.py
echo.
echo   Then open http://localhost:8050 in your browser.
echo.
echo   Optional flags for next time:
echo       setup.bat --skip-download   (skip 4+ GB dunnhumby download)
echo       setup.bat --skip-lgsr       (skip LGSR, keep Complete Journey)
echo       setup.bat --force           (re-download and re-seed everything)
echo.

endlocal
exit /b 0
