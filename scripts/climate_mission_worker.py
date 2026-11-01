"""ATLAS climate mission worker: public, owner-submitted GitHub issue requests only."""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com"
REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GITHUB_TOKEN"]
ISSUE = int(os.environ["MISSION_ISSUE_NUMBER"])
OWNER = REPO.split("/")[0]
HEADERS = {"Authorization": "Bearer " + TOKEN, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "ATLAS-Climate-Worker/0.1"}

def github(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API + path, data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)

def weather(lat, lon):
    params = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "current": "temperature_2m,precipitation,wind_speed_10m", "hourly": "precipitation", "forecast_days": 2, "timezone": "UTC"})
    req = urllib.request.Request("https://api.open-meteo.com/v1/forecast?" + params, headers={"User-Agent": "ATLAS-Climate-Worker/0.1"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

def main():
    issue = github("GET", f"/repos/{REPO}/issues/{ISSUE}")
    if issue.get("pull_request") or issue.get("user", {}).get("login", "").lower() != OWNER.lower():
        raise ValueError("Only issues opened by repository owner are eligible")
    title = issue.get("title", "")
    if not title.startswith("ATLAS climate investigation: "):
        raise ValueError("Issue is not an ATLAS climate request")
    body = issue.get("body") or ""
    match = re.search(r"Coordinates:\s*([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)", body)
    if not match:
        raise ValueError("Missing coordinates")
    lat, lon = map(float, match.groups())
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Coordinates out of range")
    data = weather(lat, lon)
    current = data["current"]
    times = data["hourly"]["time"]
    rains = data["hourly"]["precipitation"]
    now = current["time"]
    upcoming = [float(v) for t, v in zip(times, rains) if t >= now and v is not None][:24]
    rain24 = round(sum(upcoming), 2)
    name = title[len("ATLAS climate investigation: "):][:100]
    fetched = datetime.now(timezone.utc).isoformat()
    report = (f"ATLAS automated reference-weather report for {name}. "
              f"At {now} UTC: temperature {current['temperature_2m']} °C; "
              f"precipitation {current['precipitation']} mm; wind {current['wind_speed_10m']} km/h. "
              f"Next {len(upcoming)} hourly precipitation values sum to {rain24} mm. "
              f"Source: Open-Meteo forecast API, fetched {fetched}. "
              "This is third-party model/reference data, not an independently validated ATLAS prediction or a local station observation.")
    state = {"schema_version": "atlas.shared.public.v1", "mission_id": f"CLIMATE-ISSUE-{ISSUE}", "status": "reference_report_published", "updated_at_utc": fetched,
             "location": {"name": name, "latitude": lat, "longitude": lon},
             "message": report, "source": "Open-Meteo Forecast API", "source_url": "https://open-meteo.com/",
             "agent_connected": True, "publisher": "ATLAS GitHub Actions automated weather worker v0.1", "issue_number": ISSUE}
    import base64
    path = "data/shared_mission.json"
    current_file = github("GET", f"/repos/{REPO}/contents/{path}")
    github("PUT", f"/repos/{REPO}/contents/{path}", {"message": f"Publish automated climate report for issue #{ISSUE}", "content": base64.b64encode((json.dumps(state, indent=2) + "\n").encode()).decode(), "sha": current_file["sha"], "branch": "main"})
    github("POST", f"/repos/{REPO}/issues/{ISSUE}/comments", {"body": "ATLAS automated investigation completed.\n\n" + report + "\n\nDashboard: https://" + OWNER + ".github.io/" + REPO.split("/")[1] + "/\n\nNote: dashboard displays the most recently published mission only."})
    print(f"Published issue #{ISSUE} report")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Mission processing failed: {exc}", file=sys.stderr)
        raise
