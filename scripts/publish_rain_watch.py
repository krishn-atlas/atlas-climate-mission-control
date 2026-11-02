"""Publish a safe, independently collected public reference rain outlook."""
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

LAT, LON = 13.12, 80.21

def build(payload, fetched):
    current = payload["current"]
    hourly = payload["hourly"]
    times, rain = hourly["time"], hourly["precipitation"]
    if len(times) != len(rain):
        raise ValueError("Mismatched forecast arrays")
    start = datetime.fromisoformat(current["time"]).replace(tzinfo=timezone.utc)
    selected = [(t, v) for t, v in zip(times, rain)
                if start <= datetime.fromisoformat(t).replace(tzinfo=timezone.utc) < start + timedelta(hours=24)]
    valid = [float(v) for _, v in selected if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1000]
    return {
        "schema_version": "atlas.public.rain_watch.v1",
        "type": "independently_collected_public_reference_forecast",
        "fetched_at_utc": fetched.isoformat(),
        "location": {"name": "Chennai reference grid", "latitude": LAT, "longitude": LON},
        "source": "Open-Meteo Forecast API",
        "forecast_valid_from_utc": current["time"] + "Z",
        "next_24h_forecast_rain_mm": round(sum(valid), 2) if len(valid) == len(selected) and selected else None,
        "forecast_hours": len(valid),
        "current_reference_precipitation_mm": current.get("precipitation"),
        "limitations": "Public feed collected separately from private CL-004. Forecast, not observed Padi rainfall or ATLAS model prediction."
    }

def main():
    params = urllib.parse.urlencode({"latitude": LAT, "longitude": LON, "current": "precipitation", "hourly": "precipitation", "forecast_days": 2, "timezone": "UTC"})
    req = urllib.request.Request("https://api.open-meteo.com/v1/forecast?" + params, headers={"User-Agent": "ATLAS-Public-Rain-Watch/0.1"})
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.load(response)
    result = build(payload, datetime.now(timezone.utc))
    path = Path("data/rain_watch.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Published public reference forecast, hours:", result["forecast_hours"])

if __name__ == "__main__":
    main()
