"""Download satellite imagery around a point as overlapping lat_lon.jpg tiles.

Google Static Maps (best detail; needs an API key with billing enabled):
    $env:GOOGLE_MAPS_API_KEY = "..."
    python fetch_tiles.py --provider google --size 600 --zoom 20 --out PCCOE_IMAGES
Esri World Imagery (no key, but real detail stops at about zoom 18, so tiles are soft):
    python fetch_tiles.py --provider esri --size 600 --out PCCOE_IMAGES

Imagery is subject to each provider's terms; keep the tiles private and keep attribution.
"""
import argparse, io, math, os, sys, time
from pathlib import Path
import requests
from PIL import Image

ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
GOOGLE = 'https://maps.googleapis.com/maps/api/staticmap'
TS = 256
LOGO_CROP = 40  # px trimmed top and bottom (scale 2) to drop the Google logo; keeps the centre fixed


def mpp_at(lat, z):
    return 156543.03392 * math.cos(math.radians(lat)) / 2 ** z


def to_tile(lat, lon, z):
    n = 2 ** z
    return (lon + 180) / 360 * n, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n


def to_latlon(x, y, z):
    n = 2 ** z
    return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n)))), x / n * 360 - 180


def save(img, out, lat, lon):
    img.save(out / f'{lat:.6f}_{lon:.6f}.jpg', quality=95, subsampling=0)


def google_tiles(a, out):
    key = a.key or os.environ.get('GOOGLE_MAPS_API_KEY')
    if not key:
        sys.exit('Set GOOGLE_MAPS_API_KEY (or pass --key).')
    zoom = min(a.zoom, 21)
    px = 1280 - 2 * LOGO_CROP  # kept height; width stays 1280
    ground_w = mpp_at(a.lat, zoom) * 1280 / 2   # scale=2 halves metres per pixel
    ground_h = mpp_at(a.lat, zoom) * px / 2
    step_x = ground_w * (1 - a.overlap); step_y = ground_h * (1 - a.overlap)
    nx = max(1, math.ceil((a.size - ground_w) / step_x) + 1)
    ny = max(1, math.ceil((a.size - ground_h) / step_y) + 1)
    total = nx * ny
    print(f'{total} Google requests, each tile ~{ground_w:.0f} m x {ground_h:.0f} m, {mpp_at(a.lat, zoom)/2:.3f} m/px')
    if total > a.max_requests:
        sys.exit(f'{total} requests exceeds --max-requests {a.max_requests}; shrink --size or raise the cap.')
    m_lat = 111320.0; m_lon = 111320.0 * math.cos(math.radians(a.lat))
    s = requests.Session()
    for j in range(ny):
        for i in range(nx):
            dx = (i - (nx - 1) / 2) * step_x; dy = ((ny - 1) / 2 - j) * step_y
            lat = a.lat + dy / m_lat; lon = a.lon + dx / m_lon
            r = s.get(GOOGLE, timeout=30, params=dict(center=f'{lat},{lon}', zoom=zoom, size='640x640',
                                                      scale=2, maptype='satellite', format='jpg', key=key))
            if r.status_code != 200 or not r.headers.get('content-type', '').startswith('image'):
                sys.exit(f'Google error {r.status_code}: {r.text[:200]}')
            img = Image.open(io.BytesIO(r.content)).convert('RGB')
            save(img.crop((0, LOGO_CROP, img.width, img.height - LOGO_CROP)), out, lat, lon)
            time.sleep(0.05)
    return total


def esri_tiles(a, out):
    z = a.zoom
    mpp = mpp_at(a.lat, z)
    half = a.size / 2 / mpp / TS
    cx, cy = to_tile(a.lat, a.lon, z)
    x0, x1 = math.floor(cx - half), math.floor(cx + half)
    y0, y1 = math.floor(cy - half), math.floor(cy + half)
    print(f'{(x1-x0+1)*(y1-y0+1)} Esri source tiles, {mpp:.2f} m/px')
    canvas = Image.new('RGB', ((x1 - x0 + 1) * TS, (y1 - y0 + 1) * TS))
    s = requests.Session(); s.headers['User-Agent'] = 'map-matching-tile-fetcher/2.0'
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            r = s.get(ESRI.format(z=z, x=x, y=y), timeout=30); r.raise_for_status()
            canvas.paste(Image.open(io.BytesIO(r.content)).convert('RGB'), ((x - x0) * TS, (y - y0) * TS))
            time.sleep(0.05)
    side = int(a.size / mpp)
    left = max(0, int((cx - x0) * TS - side / 2)); top = max(0, int((cy - y0) * TS - side / 2))
    canvas = canvas.crop((left, top, min(canvas.width, left + side), min(canvas.height, top + side)))
    stride = max(1, int(a.tile * (1 - a.overlap))); n = 0
    for ty in range(0, max(1, canvas.height - a.tile + 1), stride):
        for tx in range(0, max(1, canvas.width - a.tile + 1), stride):
            lat, lon = to_latlon(x0 + (left + tx + a.tile / 2) / TS, y0 + (top + ty + a.tile / 2) / TS, z)
            save(canvas.crop((tx, ty, tx + a.tile, ty + a.tile)), out, lat, lon); n += 1
    return n


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--provider', choices=['google', 'esri'], default='google')
    p.add_argument('--lat', type=float, default=18.6531795)
    p.add_argument('--lon', type=float, default=73.7633268)
    p.add_argument('--size', type=float, default=600, help='side of the square area in metres')
    p.add_argument('--zoom', type=int, default=None, help='google: 19-21 (default 20); esri: default 18 (its real limit)')
    p.add_argument('--tile', type=int, default=640, help='esri only: output tile px')
    p.add_argument('--overlap', type=float, default=0.5)
    p.add_argument('--key', default=None, help='Google API key (or env GOOGLE_MAPS_API_KEY)')
    p.add_argument('--max-requests', type=int, default=400, help='google safety cap')
    p.add_argument('--out', default='PCCOE_IMAGES')
    a = p.parse_args()
    a.zoom = a.zoom or (20 if a.provider == 'google' else 18)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    n = google_tiles(a, out) if a.provider == 'google' else esri_tiles(a, out)
    print(f'wrote {n} tiles to {out}')


if __name__ == '__main__':
    main()
