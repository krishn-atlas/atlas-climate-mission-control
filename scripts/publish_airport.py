"""Publish only public AWC VOMM weather; no private repository access."""
import json
import math
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = 'https://aviationweather.gov/api/data/metar?ids=VOMM&format=json'

def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None

def normalize(records, now):
    candidates = [r for r in records if isinstance(r, dict) and r.get('icaoId') == 'VOMM' and number(r.get('obsTime')) is not None]
    if not candidates:
        raise ValueError('No timestamped VOMM report')
    r = max(candidates, key=lambda x: x['obsTime'])
    observed = datetime.fromtimestamp(r['obsTime'], timezone.utc)
    age = (now - observed).total_seconds() / 60
    if age < -5 or age > 120:
        raise ValueError('Report outside freshness window')
    if not isinstance(r.get('rawOb'), str) or not r['rawOb'].strip():
        raise ValueError('Missing raw observation')
    speed = number(r.get('wspd'))
    if speed is not None and speed < 0:
        speed = None
    visibility = r.get('visib')
    if not isinstance(visibility, (str, int, float)) or isinstance(visibility, bool):
        visibility = None
    return {
        'schema_version': 'atlas.airport.public.v1',
        'station': 'VOMM', 'station_name': 'Chennai Airport',
        'source': 'NOAA Aviation Weather Center', 'source_url': URL,
        'observed_at_utc': observed.isoformat(), 'fetched_at_utc': now.isoformat(),
        'temperature_c': number(r.get('temp')),
        'wind_kmh': round(speed * 1.852, 1) if speed is not None else None,
        'visibility_statute_miles': visibility,
        'altimeter_hpa': number(r.get('altim')),
        'raw_report': r['rawOb'],
        'note': 'Airport-local observation, not citywide ground truth. No rainfall total or forecast accuracy inferred.',
    }

def main():
    request = urllib.request.Request(URL, headers={'User-Agent': 'ATLAS-Climate-Public/0.2', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(500001)
    if len(raw) > 500000:
        raise ValueError('Response too large')
    records = json.loads(raw)
    if not isinstance(records, list):
        raise ValueError('Expected list')
    result = normalize(records, datetime.now(timezone.utc))
    destination = Path('data/airport.json')
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print('Published observation:', result['observed_at_utc'])

if __name__ == '__main__':
    main()
