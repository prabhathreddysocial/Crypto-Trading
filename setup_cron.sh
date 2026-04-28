#!/bin/bash
# Run this once on the VM to install the correct crontab.
# Usage: bash setup_cron.sh

USER_HOME="/home/srisaiprabhathreddygudipalli"
DIR="$USER_HOME/Crypto-Trading"
PY="/usr/bin/python3"

crontab - <<CRON
0 * * * * cd $DIR && $PY hourly_trader.py >> logs/hourly.log 2>&1
0 0 * * * cd $DIR && $PY daily_summary.py >> logs/daily.log 2>&1
0 0 * * 0 cd $DIR && $PY weekly_review.py >> logs/weekly.log 2>&1
0 0 1 * * cd $DIR && $PY monthly_review.py >> logs/monthly.log 2>&1
CRON

echo "Crontab installed:"
crontab -l
