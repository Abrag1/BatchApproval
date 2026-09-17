@echo off
REM Double-click this file to run the ClearCheck dashboard on your own computer.
REM It installs the required packages (first run only, ~1-2 minutes) and then
REM opens the dashboard in your web browser at http://localhost:8501
REM
REM To stop the dashboard: close this window, or press Ctrl+C inside it.

cd /d "%~dp0"

echo Installing/checking required packages...
python -m pip install -r requirements.txt --quiet

echo.
echo Starting the dashboard... your browser will open automatically.
echo (Keep this window open while you use the dashboard. Close it when done.)
echo.

python -m streamlit run app.py

pause
