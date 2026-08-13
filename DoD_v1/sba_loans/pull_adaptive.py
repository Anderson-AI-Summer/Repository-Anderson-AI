# -*- coding: utf-8 -*-
import json, time, os, zipfile, io, urllib.request, urllib.error
from datetime import date, timedelta

OUTDIR = r"C:\finances\data\sba_loans\offers_fullrange"
LOG = r"C:\finances\data\sba_loans\offers_adaptive_log.csv"
os.makedirs(OUTDIR, exist_ok=True)

MIN_DELAY = 2.5          # seconds between ANY two API calls, always
MAX_RETRIES_SAME = 2     # retries at the same granularity before splitting
MAX_SPLIT_DEPTH = 4      # month -> ~half -> ~quarter -> week -> stop (don't go below ~4 days)

_last_call_time = [0.0]

def throttle():
    elapsed = time.time() - _last_call_time[0]
    if elapsed < MIN_DELAY:
        time.sleep(MIN_DELAY - elapsed)
    _last_call_time[0] = time.time()

def log(line):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def post_json(url, payload, timeout=30):
    throttle()
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_json(url, timeout=30):
    throttle()
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def submit_and_wait(start, end, max_poll=25, poll_sleep=5):
    payload = {
        "filters": {
            "award_type_codes": ["D"],
            "agencies": [{"type": "awarding", "tier": "toptier", "name": "Department of Defense"}],
            "time_period": [{"start_date": start, "end_date": end, "date_type": "action_date"}],
        },
        "columns": [],
    }
    try:
        resp = post_json("https://api.usaspending.gov/api/v2/download/awards/", payload, timeout=30)
    except Exception as e:
        return None, f"submit_error:{e}"
    fname = resp.get("file_name")
    if not fname:
        return None, "no_filename"
    status_url = f"https://api.usaspending.gov/api/v2/download/status?file_name={fname}"
    for _ in range(max_poll):
        time.sleep(poll_sleep)
        try:
            r2 = get_json(status_url, timeout=30)
        except Exception:
            continue
        status = r2.get("status")
        if status == "finished":
            return fname, "finished"
        if status == "failed":
            return None, "failed"
    return None, "timeout"

def download_and_extract(fname, outfile, attempts=2):
    file_url = f"https://files.usaspending.gov/generated_downloads/{fname}"
    for attempt in range(attempts):
        try:
            throttle()
            req = urllib.request.Request(file_url)
            with urllib.request.urlopen(req, timeout=60) as resp:
                blob = resp.read()
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                for name in z.namelist():
                    if name.startswith("Contracts_PrimeAwardSummaries") and name.endswith(".csv"):
                        with z.open(name) as f, open(outfile, "wb") as out:
                            out.write(f.read())
                        return True
            return False
        except Exception as e:
            if attempt == attempts - 1:
                log(f"download_error:{e}")
                return False
            time.sleep(5)
    return False

def process(start_d, end_d, depth=0):
    start_s = start_d.isoformat()
    end_s = end_d.isoformat()
    outfile = os.path.join(OUTDIR, f"{start_s}_{end_s}.csv")
    if os.path.exists(outfile) and os.path.getsize(outfile) > 0:
        return True

    backoff = 5
    for attempt in range(MAX_RETRIES_SAME):
        fname, status = submit_and_wait(start_s, end_s)
        if status == "finished" and fname:
            ok = download_and_extract(fname, outfile)
            if ok:
                log(f"{start_s},{end_s},finished,depth{depth}")
                return True
            log(f"{start_s},{end_s},extract_error,depth{depth}")
        else:
            log(f"{start_s},{end_s},{status},depth{depth}_attempt{attempt+1}")
        if attempt < MAX_RETRIES_SAME - 1:
            time.sleep(backoff)
            backoff *= 2

    span_days = (end_d - start_d).days
    if span_days < 4 or depth >= MAX_SPLIT_DEPTH:
        log(f"{start_s},{end_s},PERMANENT_FAIL,depth{depth}")
        return False

    log(f"{start_s},{end_s},splitting,depth{depth}")
    mid = start_d + timedelta(days=span_days // 2)
    time.sleep(3)
    try:
        ok1 = process(start_d, mid, depth + 1)
    except Exception as ex:
        log(f"{start_d},{mid},UNCAUGHT_ERROR:{ex},depth{depth+1}")
        ok1 = False
    time.sleep(3)
    try:
        ok2 = process(mid + timedelta(days=1), end_d, depth + 1)
    except Exception as ex:
        log(f"{mid + timedelta(days=1)},{end_d},UNCAUGHT_ERROR:{ex},depth{depth+1}")
        ok2 = False
    return ok1 and ok2

def month_ranges(start_year, start_month, end_year, end_month):
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        first = date(y, m, 1)
        if m == 12:
            next_first = date(y + 1, 1, 1)
        else:
            next_first = date(y, m + 1, 1)
        last = next_first - timedelta(days=1)
        yield first, last
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1

if __name__ == "__main__":
    months = list(month_ranges(2019, 10, 2026, 4))
    print(f"Total months to process: {len(months)}")
    for i, (s, e) in enumerate(months):
        print(f"[{i+1}/{len(months)}] {s} to {e}")
        try:
            process(s, e)
        except Exception as ex:
            log(f"{s},{e},UNCAUGHT_ERROR:{ex},depth0")
        time.sleep(2)
    print("ALL_DONE")
