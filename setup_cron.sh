#!/bin/bash
# Run this once on the VM to install the correct crontab.
# Uses wrapper scripts (run_hourly, run_daily, etc.) so no .py
# filenames appear in the crontab — avoiding any markdown conversion issues.
# Usage: bash setup_cron.sh

DIR="/home/srisaiprabhathreddygudipalli/Crypto-Trading"

# Make wrapper scripts executable
chmod +x "$DIR/run_hourly" "$DIR/run_daily" "$DIR/run_weekly" "$DIR/run_monthly"

# Install clean crontab — no .py filenames anywhere
crontab - <<CRON
0 * * * * $DIR/run_hourly >> $DIR/logs/hourly.log 2>&1
0 0 * * * $DIR/run_daily >> $DIR/logs/daily.log 2>&1
0 0 * * 0 $DIR/run_weekly >> $DIR/logs/weekly.log 2>&1
0 0 1 * * $DIR/run_monthly >> $DIR/logs/monthly.log 2>&1
CRON

echo "Crontab installed:"
crontab -l
