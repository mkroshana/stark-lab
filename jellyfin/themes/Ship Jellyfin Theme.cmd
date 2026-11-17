@echo off
rem One click: build, check and (after you confirm) deploy the NeutralFin Jellyfin theme.
rem Runs ship.sh in Git Bash and keeps the window open so you can read the result.
"%ProgramFiles%\Git\bin\bash.exe" --login -c "cd \"$(cygpath -u '%~dp0')\" && ./ship.sh"
echo.
pause
