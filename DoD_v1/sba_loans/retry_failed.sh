#!/bin/bash
set -uo pipefail

OUTDIR="/c/finances/data/sba_loans/daily"
LOG="/c/finances/data/sba_loans/pull_log.csv"
FAILLOG="/c/finances/data/sba_loans/failed_days.txt"
STILLFAILED="/c/finances/data/sba_loans/failed_days_retry2.txt"
: > "$STILLFAILED"

while IFS= read -r d; do
  [ -z "$d" ] && continue
  OUTFILE="$OUTDIR/${d}.csv"
  if [ -f "$OUTFILE" ] && [ -s "$OUTFILE" ]; then
    continue
  fi

  ATTEMPT=0
  SUCCESS=0
  while [ $ATTEMPT -lt 3 ] && [ $SUCCESS -eq 0 ]; do
    ATTEMPT=$((ATTEMPT+1))
    RESP=$(curl -s -4 -m 30 -X POST "https://api.usaspending.gov/api/v2/download/awards/" \
      -H "Content-Type: application/json" \
      -d "{
        \"filters\": {
          \"award_type_codes\": [\"08\"],
          \"agencies\": [{\"type\":\"awarding\",\"tier\":\"toptier\",\"name\":\"Small Business Administration\"}],
          \"time_period\": [{\"start_date\":\"$d\",\"end_date\":\"$d\",\"date_type\":\"action_date\"}],
          \"place_of_performance_locations\": [{\"country\":\"USA\",\"state\":\"CA\"}]
        },
        \"columns\": []
      }")
    FNAME=$(echo "$RESP" | grep -o '"file_name":"[^"]*"' | head -1 | cut -d'"' -f4)
    if [ -z "$FNAME" ]; then
      echo "$d,submit_error,,," >> "$LOG"
      sleep 5
      continue
    fi

    STATUS=""
    for i in $(seq 1 25); do
      sleep 4
      R2=$(curl -s -4 -m 30 "https://api.usaspending.gov/api/v2/download/status?file_name=$FNAME")
      STATUS=$(echo "$R2" | grep -o '"status":"[a-z]*"' | head -1 | cut -d'"' -f4)
      if [ "$STATUS" = "finished" ] || [ "$STATUS" = "failed" ]; then
        break
      fi
    done

    if [ "$STATUS" = "finished" ]; then
      ROWS=$(echo "$R2" | grep -o '"total_rows":[0-9]*' | grep -o '[0-9]*')
      SIZE=$(echo "$R2" | grep -o '"total_size":[0-9.]*' | grep -o '[0-9.]*$')
      FILEURL="https://files.usaspending.gov/generated_downloads/$FNAME"
      TMPZIP="$OUTDIR/${d}.zip"
      curl -s -4 -m 60 -o "$TMPZIP" "$FILEURL"
      unzip -p "$TMPZIP" "*.csv" > "$OUTFILE" 2>/dev/null
      if [ -s "$OUTFILE" ]; then
        rm -f "$TMPZIP"
        echo "$d,finished,$ROWS,$SIZE," >> "$LOG"
        SUCCESS=1
      else
        echo "$d,extract_error,,," >> "$LOG"
      fi
    else
      echo "$d,failed_attempt$ATTEMPT,,," >> "$LOG"
      sleep 5
    fi
  done

  if [ $SUCCESS -eq 0 ]; then
    echo "$d" >> "$STILLFAILED"
  fi
done < "$FAILLOG"

echo "RETRY_DONE"
