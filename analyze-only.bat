@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"

set "LLM_MODEL=%~1"
set "OUT_DIR=%~2"
set "LOG_FILE=%~dp0analyze-only.log"

echo Starting analyze-only at %DATE% %TIME% > "%LOG_FILE%"
echo Working directory: %CD% >> "%LOG_FILE%"

if not "%~1"=="" (
    if not "%~2"=="" (
        echo Running: python -m reddit_pain_search "_all_" --analyze-only --llm-model "%~1" --out "%~2/reddit-pain-search.csv" >> "%LOG_FILE%"
        python -m reddit_pain_search "_all_" --analyze-only --llm-model "%~1" --out "%~2/reddit-pain-search.csv" >> "%LOG_FILE%" 2>&1
    ) else (
        echo Running: python -m reddit_pain_search "_all_" --analyze-only --llm-model "%~1" >> "%LOG_FILE%"
        python -m reddit_pain_search "_all_" --analyze-only --llm-model "%~1" >> "%LOG_FILE%" 2>&1
    )
) else (
    if not "%~2"=="" (
        echo Running: python -m reddit_pain_search "_all_" --analyze-only --out "%~2/reddit-pain-search.csv" >> "%LOG_FILE%"
        python -m reddit_pain_search "_all_" --analyze-only --out "%~2/reddit-pain-search.csv" >> "%LOG_FILE%" 2>&1
    ) else (
        echo Running: python -m reddit_pain_search "_all_" --analyze-only >> "%LOG_FILE%"
        python -m reddit_pain_search "_all_" --analyze-only >> "%LOG_FILE%" 2>&1
    )
)
set "EXIT_CODE=%ERRORLEVEL%"

echo Finished with exit code %EXIT_CODE% at %DATE% %TIME% >> "%LOG_FILE%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo analyze-only failed with exit code %EXIT_CODE%. See analyze-only.log for details.
) else (
    echo.
    echo analyze-only completed. See analyze-only.log for details.
)

echo.
echo Log saved to: %LOG_FILE%
pause
exit /b %EXIT_CODE%

