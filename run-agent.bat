@echo off
setlocal

cd /d "%~dp0"

set "PRODUCT_NAME=%~1"
if "%PRODUCT_NAME%"=="" (
    set /p "PRODUCT_NAME=Product to search, for example Notion: "
)

set "LIMIT_POSTS=%~2"
if "%LIMIT_POSTS%"=="" (
    set /p "LIMIT_POSTS=Number of posts to read [10]: "
)
if "%LIMIT_POSTS%"=="" (
    set "LIMIT_POSTS=10"
)

set "COMMENTS_PER_POST=%~3"
if "%COMMENTS_PER_POST%"=="" (
    set /p "COMMENTS_PER_POST=Comments per post [3]: "
)
if "%COMMENTS_PER_POST%"=="" (
    set "COMMENTS_PER_POST=3"
)

if "%PRODUCT_NAME%"=="" (
    echo Product name is required.
    pause
    exit /b 2
)

set "SEARCH_SCROLLS=%~4"
if "%SEARCH_SCROLLS%"=="" (
    powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\run-agent.ps1" "%PRODUCT_NAME%" -LimitPosts %LIMIT_POSTS% -CommentsPerPost %COMMENTS_PER_POST%
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\run-agent.ps1" "%PRODUCT_NAME%" -LimitPosts %LIMIT_POSTS% -CommentsPerPost %COMMENTS_PER_POST% -SearchScrolls %SEARCH_SCROLLS%
)
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo run-agent failed with exit code %EXIT_CODE%.
)

echo.
pause
exit /b %EXIT_CODE%
