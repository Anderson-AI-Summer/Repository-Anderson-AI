#!/bin/bash
set -uo pipefail

OUTDIR="/c/finances/data/sba_loans/offers_fullrange"
LOG="/c/finances/data/sba_loans/offers_fullrange_log.csv"
mkdir -p "$OUTDIR"
if [ ! -f "$LOG" ]; then
  echo "month_start,status,rows,size_kb" > "$LOG"
fi

MONTHS=(
  "2019-10-01,2019-10-31" "2019-11-01,2019-11-30" "2019-12-01,2019-12-31"
  "2020-01-01,2020-01-31" "2020-02-01,2020-02-29" "2020-03-01,2020-03-31"
  "2020-04-01,2020-04-30" "2020-05-01,2020-05-31" "2020-06-01,2020-06-30"
  "2020-07-01,2020-07-31" "2020-08-01,2020-08-31" "2020-09-01,2020-09-30"
  "2020-10-01,2020-10-31" "2020-11-01,2020-11-30" "2020-12-01,2020-12-31"
  "2021-01-01,2021-01-31" "2021-02-01,2021-02-28" "2021-03-01,2021-03-31"
  "2021-04-01,2021-04-30" "2021-05-01,2021-05-31" "2021-06-01,2021-06-30"
  "2021-07-01,2021-07-31" "2021-08-01,2021-08-31" "2021-09-01,2021-09-30"
  "2021-10-01,2021-10-31" "2021-11-01,2021-11-30" "2021-12-01,2021-12-31"
  "2022-01-01,2022-01-31" "2022-02-01,2022-02-28" "2022-03-01,2022-03-31"
  "2022-04-01,2022-04-30" "2022-05-01,2022-05-31" "2022-06-01,2022-06-30"
  "2022-07-01,2022-07-31" "2022-08-01,2022-08-31" "2022-09-01,2022-09-30"
  "2022-10-01,2022-10-31" "2022-11-01,2022-11-30" "2022-12-01,2022-12-31"
  "2023-01-01,2023-01-31" "2023-02-01,2023-02-28" "2023-03-01,2023-03-31"
  "2023-04-01,2023-04-30" "2023-05-01,2023-05-31" "2023-06-01,2023-06-30"
  "2023-07-01,2023-07-31" "2023-08-01,2023-08-31" "2023-09-01,2023-09-30"
  "2023-10-01,2023-10-31" "2023-11-01,2023-11-30" "2023-12-01,2023-12-31"
  "2024-01-01,2024-01-31" "2024-02-01,2024-02-29" "2024-03-01,2024-03-31"
  "2024-04-01,2024-04-30" "2024-05-01,2024-05-31" "2024-06-01,2024-06-30"
  "2024-07-01,2024-07-31" "2024-08-01,2024-08-31" "2024-09-01,2024-09-30"
  "2024-10-01,2024-10-15" "2024-10-16,2024-10-31" "2024-11-01,2024-11-30" "2024-12-01,2024-12-31"
  "2025-01-01,2025-01-31" "2025-02-01,2025-02-28" "2025-03-01,2025-03-31"
  "2025-04-01,2025-04-30" "2025-05-01,2025-05-31" "2025-06-01,2025-06-30"
  "2025-07-01,2025-07-31" "2025-08-01,2025-08-31" "2025-09-01,2025-09-30"
  "2025-10-01,2025-10-31" "2025-11-01,2025-11-30" "2025-12-01,2025-12-31"
  "2026-01-01,2026-01-31" "2026-02-01,2026-02-28" "2026-03-01,2026-03-31"
  "2026-04-01,2026-04-30"
)

for RANGE in "${MONTHS[@]}"; do
  START=$(echo $RANGE | cut -d, -f1)
  END=$(echo $RANGE | cut -d, -f2)
  OUTFILE="$OUTDIR/${START}.csv"
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
          \"award_type_codes\": [\"D\"],
          \"agencies\": [{\"type\":\"awarding\",\"tier\":\"toptier\",\"name\":\"Department of Defense\"}],
          \"time_period\": [{\"start_date\":\"$START\",\"end_date\":\"$END\",\"date_type\":\"action_date\"}]
        },
        \"columns\": []
      }")
    FNAME=$(echo "$RESP" | grep -o '"file_name":"[^"]*"' | head -1 | cut -d'"' -f4)
    if [ -z "$FNAME" ]; then
      echo "$START,submit_error,," >> "$LOG"
      sleep 5
      continue
    fi

    STATUS=""
    for i in $(seq 1 25); do
      sleep 5
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
      TMPZIP="$OUTDIR/${START}.zip"
      curl -s -4 -m 60 -o "$TMPZIP" "$FILEURL"
      unzip -p "$TMPZIP" "Contracts_PrimeAwardSummaries*.csv" > "$OUTFILE" 2>/dev/null
      if [ -s "$OUTFILE" ]; then
        rm -f "$TMPZIP"
        echo "$START,finished,$ROWS,$SIZE" >> "$LOG"
        SUCCESS=1
      else
        echo "$START,extract_error,," >> "$LOG"
      fi
    else
      echo "$START,failed_attempt$ATTEMPT,," >> "$LOG"
      sleep 5
    fi
  done
done

echo "ALL_MONTHS_DONE"
