@echo off
chcp 65001 > nul
title iPhone Album Sorter ^& Deduplicator

echo ====================================================================
echo   📱 iPhone Album Sorter ^& Deduplicator Tool
echo ====================================================================
echo.

python filter_albums.py
pause
