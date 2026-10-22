# -*- coding: utf-8 -*-
"""Скачивает данные OpenStreetMap для села Покровское и сохраняет их в osm_all.pkl.

Запуск из корня проекта:

    python examples/download_osm_pokrovskoe.py

Скрипт перебирает несколько серверов Overpass (они часто перегружены),
поэтому один и тот же запрос повторяется до первого успешного ответа.
Результат — файл examples/data/pokrovskoe/osm_all.pkl, который читает ноутбук
blocksnet_pokrovskoe.ipynb.
"""
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import geopandas as gpd
import osmnx.features as oxf
import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "pokrovskoe"
OUT = DATA / "osm_all.pkl"

TAG_KEYS = {
    "highway", "railway", "building", "landuse", "natural", "waterway", "water",
    "riverbank", "reservoir", "basin", "dock", "canal", "pond",
    "amenity", "shop", "leisure", "tourism",
}

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def main():
    boundary = gpd.read_file(DATA / "boundary.geojson").to_crs(4326)
    minx, miny, maxx, maxy = boundary.total_bounds
    bbox = f"{miny},{minx},{maxy},{maxx}"
    print("Граница территории:", DATA / "boundary.geojson")
    print("BBox:", bbox)

    query = f"""[out:json][timeout:900][bbox:{bbox}];
(
  way["highway"];
  way["railway"="rail"];
  way["building"];
  way["landuse"];
  way["natural"];
  way["waterway"];
  way["water"];
  way["riverbank"];
  way["reservoir"];
  way["basin"];
  way["dock"];
  way["canal"];
  way["pond"];
  nwr["amenity"];
  nwr["shop"];
  nwr["leisure"];
  nwr["tourism"];
);
(._;>;);
out;"""

    payload = None
    for attempt in range(1, 4):
        for url in ENDPOINTS:
            print(f"[попытка {attempt}] {url}", flush=True)
            t0 = time.time()
            try:
                response = requests.post(
                    url,
                    data={"data": query},
                    timeout=950,
                    headers={"User-Agent": "idu-practice/1.0 (educational)"},
                )
                if response.status_code != 200:
                    print(f"  HTTP {response.status_code} за {time.time()-t0:.1f}s", flush=True)
                    continue
                payload = response.json()
                print(f"  получено {len(payload['elements'])} элементов за {time.time()-t0:.1f}s", flush=True)
                break
            except Exception as exc:
                print(f"  ошибка за {time.time()-t0:.1f}s: {type(exc).__name__}: {exc}", flush=True)
        if payload is not None:
            break
        print(f"[попытка {attempt}] не удалась, пауза 30 с", flush=True)
        time.sleep(30)

    if payload is None:
        raise SystemExit("Не удалось скачать данные OSM ни с одного сервера")

    rows = oxf._process_features(payload["elements"], TAG_KEYS)
    gdf = gpd.GeoDataFrame(data=rows, geometry="geometry", crs="EPSG:4326")
    gdf.to_pickle(OUT)
    print("Сохранено:", OUT, f"({OUT.stat().st_size // 1024} КБ)")
    print("Объектов:", len(gdf))


if __name__ == "__main__":
    main()
