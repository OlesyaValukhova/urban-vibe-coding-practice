# -*- coding: utf-8 -*-
"""
Сборка одной HTML-страницы с интерактивной картой и дашбордом
по результатам ноутбука blocksnet_pokrovskoe.ipynb.

Запуск (из активированного окружения .venv):

    python examples/make_dashboard.py

Скрипт читает готовые файлы из examples/data/pokrovskoe/
и создаёт examples/dashboard.html — один самодостаточный файл.

Используются только уже установленные библиотеки: geopandas, folium, branca,
matplotlib, pandas. Графики рисует Chart.js (подключается с CDN, как и Leaflet
внутри folium), поэтому отдельные Python-пакеты не нужны.
"""
import html as html_lib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import folium
import branca.colormap as bcm
import matplotlib
import matplotlib.colors as mcolors
from matplotlib import colormaps

# --------------------------------------------------------------- пути
HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "pokrovskoe"
OUT = HERE / "dashboard.html"

PALETTE = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
]


# --------------------------------------------------------------- чтение
def load(name, **kwargs):
    path = DATA / name
    if not path.exists():
        print(f"[нет файла] {path.name} — пропускаю")
        return None
    return gpd.read_file(path, **kwargs)


def short(name):
    """Читает слой и оставляет только geometry + нужную колонку."""
    path = DATA / name
    if not path.exists():
        return None
    return gpd.read_file(path)


results = load("results_blocks.geojson")
if results is None:
    raise SystemExit(
        "Нет results_blocks.geojson. Сначала выполните ноутбук "
        "examples/blocksnet_pokrovskoe.ipynb."
    )

boundary = load("boundary.geojson")
water = load("water.geojson")
roads = load("roads.geojson")

# матрицы времени (для честной проверки, если понадобится)
summary_csv = DATA / "results_summary.csv"
summary_df = pd.read_csv(summary_csv, index_col=0) if summary_csv.exists() else None

provision = {}
for path in sorted(DATA.glob("provision_*.geojson")):
    st = path.stem.replace("provision_", "")
    gdf = gpd.read_file(path)
    if "provision_strong" in gdf.columns:
        provision[st] = gdf

print("Кварталов в слое результатов:", len(results))
print("Слоёв обеспеченности:", len(provision))


# --------------------------------------------------------------- карта
center = results.to_crs(4326).geometry.union_all().centroid
m = folium.Map(location=[center.y, center.x], zoom_start=14,
               tiles="CartoDB positron", control_scale=True)

CATEGORICAL = {"morphotype", "land_use", "morphotype_strelka"}
NUMERIC_LAYERS = [
    ("population", "Население, чел.", "magma"),
    ("время_пешком_мин", "Среднее время пешком, мин", "viridis"),
    ("время_авто_мин", "Среднее время на авто, мин", "viridis"),
    ("area_accessibility", "Доступность по площади, мин", "coolwarm"),
    ("fsi", "FSI — плотность застройки", "YlOrRd"),
    ("gsi", "GSI — плотность застройки", "YlOrRd"),
    ("mxi", "MXI — доля жилья", "PuBu"),
]


def _feature_collection(gdf, column):
    geo = gdf.dropna(subset=[column])[["geometry", column]].to_crs(4326)
    return json.loads(geo.to_json())


def add_numeric_layer(gdf, column, name, cmap, show=False):
    if column not in gdf.columns:
        return
    geo = gdf.dropna(subset=[column])
    if geo.empty:
        return
    vals = geo[column].astype(float)
    vmin, vmax = float(vals.min()), float(vals.max())
    if vmax == vmin:
        vmax = vmin + 1.0
    colors = [mcolors.to_hex(colormaps[cmap](x))
              for x in np.linspace(0.05, 0.95, 7)]
    colormap = bcm.LinearColormap(colors=colors, vmin=vmin, vmax=vmax)

    fc = _feature_collection(gdf, column)

    def style(feature):
        v = feature["properties"].get(column)
        return {
            "fillColor": colormap(v) if v is not None else "#e0e0e0",
            "color": "#7a7a7a", "weight": 0.4, "fillOpacity": 0.75,
        }

    folium.GeoJson(
        fc, name=name, style_function=style, show=show,
        tooltip=folium.GeoJsonTooltip(fields=[column], aliases=[name + " "]),
    ).add_to(m)

    colormap.caption = name
    m.add_child(colormap)


def add_categorical_layer(gdf, column, name, show=False):
    if column not in gdf.columns:
        return
    gdf = gdf[gdf[column].notna()]
    if gdf.empty:
        return
    cats = sorted(gdf[column].astype(str).unique())
    color_map = {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(cats)}

    g = gdf.copy()
    g[column] = g[column].astype(str)
    fc = _feature_collection(g, column)

    def style(feature):
        v = feature["properties"].get(column)
        return {
            "fillColor": color_map.get(v, "#cccccc"),
            "color": "#7a7a7a", "weight": 0.4, "fillOpacity": 0.8,
        }

    folium.GeoJson(
        fc, name=name, style_function=style, show=show,
        tooltip=folium.GeoJsonTooltip(fields=[column], aliases=[name + " "]),
    ).add_to(m)


# базовые слои
for column, name, cmap in NUMERIC_LAYERS:
    add_numeric_layer(results, column, name, cmap, show=(column == "population"))
for column, name in [("morphotype", "Морфотип (Spacematrix)"),
                     ("land_use", "Land use")]:
    add_categorical_layer(results, column, name)

# контуры/подложка
if boundary is not None:
    folium.GeoJson(
        json.loads(boundary.to_crs(4326).to_json()),
        name="Граница", style_function=lambda f: {
            "fill": False, "color": "#111", "weight": 2},
    ).add_to(m)
if water is not None and len(water):
    folium.GeoJson(
        json.loads(water.to_crs(4326).to_json()),
        name="Вода", style_function=lambda f: {
            "fillColor": "#9ecae1", "color": "#6baed6", "weight": 0.5,
            "fillOpacity": 0.6},
    ).add_to(m)
if roads is not None and len(roads):
    folium.GeoJson(
        json.loads(roads.to_crs(4326).to_json()),
        name="Дороги", style_function=lambda f: {
            "color": "#888", "weight": 0.6},
        show=False,
    ).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
map_html = m.get_root().render()


# --------------------------------------------------------------- карта обеспеченности
def build_provision_map():
    """Отдельная карта: один слой кварталов, сервис выбирается из списка."""
    if not provision:
        return None

    prov_map = folium.Map(
        location=[center.y, center.x], zoom_start=14,
        tiles="CartoDB positron", control_scale=True,
    )

    if boundary is not None:
        folium.GeoJson(
            json.loads(boundary.to_crs(4326).to_json()),
            name="Граница",
            style_function=lambda f: {
                "fill": False, "color": "#111", "weight": 2},
        ).add_to(prov_map)

    # единая шкала 0..1 для всех сервисов, чтобы значения были сравнимы
    colors = [mcolors.to_hex(colormaps["RdYlGn"](x))
              for x in np.linspace(0.05, 0.95, 7)]
    colormap = bcm.LinearColormap(colors=colors, vmin=0.0, vmax=1.0)

    services = [st for st, gdf in provision.items()
                if "provision_strong" in gdf.columns]
    if not services:
        return None

    # один FeatureCollection: геометрия кварталов + значение и цвет по каждому сервису
    fc = json.loads(results.to_crs(4326)[["geometry"]].to_json())
    values = {
        st: provision[st]["provision_strong"].reindex(results.index)
        for st in services
    }

    for i, feature in enumerate(fc["features"]):
        props = feature["properties"]
        for st in services:
            v = values[st].iloc[i] if i < len(values[st]) else None
            if v is None or pd.isna(v):
                props[st] = None
                props[f"c_{st}"] = "#e0e0e0"
            else:
                props[st] = round(float(v), 3)
                props[f"c_{st}"] = colormap(float(v))

    first = services[0]
    gj = folium.GeoJson(
        fc,
        name="Обеспеченность",
        style_function=lambda f: {
            "fillColor": f["properties"].get(f"c_{first}", "#e0e0e0"),
            "color": "#7a7a7a", "weight": 0.4, "fillOpacity": 0.75,
        },
    )
    gj.add_to(prov_map)

    options = "".join(f'<option value="{st}">{st}</option>'
                      for st in services)
    control_html = f"""
    <div style="position:absolute;top:12px;right:12px;z-index:9999;background:#fff;
         padding:10px 12px;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,.18);
         font:13px/1.4 -apple-system,'Segoe UI',Arial,sans-serif">
      <div style="font-weight:600;margin-bottom:6px">Обеспеченность сервисом</div>
      <select id="prov-select" style="width:190px;padding:4px">{options}</select>
      <div style="margin-top:8px;height:10px;border-radius:3px;
           background:linear-gradient(to right,{colors[0]},{colors[3]},{colors[-1]})"></div>
      <div style="display:flex;justify-content:space-between;color:#5b6b7a;font-size:11px">
        <span>0 — нет доступа</span><span>1 — норматив</span>
      </div>
    </div>
    """
    prov_map.get_root().html.add_child(folium.Element(control_html))

    layer_name = gj.get_name()
    script = f"""
    <script>
    window.addEventListener('load', function () {{
      var layer = window["{layer_name}"];
      var sel = document.getElementById('prov-select');

      function apply(service) {{
        layer.eachLayer(function (l) {{
          var p = l.feature.properties;
          l.setStyle({{ fillColor: p['c_' + service] || '#e0e0e0' }});
          var v = p[service];
          var text = (v === null || v === undefined)
            ? service + ': нет данных'
            : service + ': ' + Number(v).toFixed(2);
          l.unbindTooltip();
          l.bindTooltip(text, {{ sticky: true }});
        }});
      }}

      sel.addEventListener('change', function () {{ apply(sel.value); }});
      apply(sel.value);
    }});
    </script>
    """
    prov_map.get_root().html.add_child(folium.Element(script))

    return prov_map.get_root().render()


provision_html = build_provision_map()


# --------------------------------------------------------------- данные для панелей
def num(value, digits=2):
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


kpi = []
kpi.append(("Кварталов", len(results)))
if "population" in results.columns:
    kpi.append(("Население (оценка), чел.", int(results["population"].sum(skipna=True))))
if "время_пешком_мин" in results.columns:
    kpi.append(("Средн. время пешком, мин", num(results["время_пешком_мин"].mean(), 1)))
if "время_авто_мин" in results.columns:
    kpi.append(("Средн. время на авто, мин", num(results["время_авто_мин"].mean(), 1)))
if "fsi" in results.columns:
    kpi.append(("Средний FSI", num(results["fsi"].mean())))
if "gsi" in results.columns:
    kpi.append(("Средний GSI", num(results["gsi"].mean())))
kpi.append(("Сервисов с данными", len(provision)))

# 1. время в пути: пешком vs авто
time_chart = {"labels": [], "values": []}
if "время_пешком_мин" in results.columns:
    time_chart["labels"].append("пешком")
    time_chart["values"].append(num(results["время_пешком_мин"].mean(), 1))
if "время_авто_мин" in results.columns:
    time_chart["labels"].append("на авто")
    time_chart["values"].append(num(results["время_авто_мин"].mean(), 1))

# 2. обеспеченность сервисами
prov_sorted = sorted(provision.items(),
                     key=lambda kv: float(kv[1]["provision_strong"].mean()),
                     reverse=True)[:14]
prov_chart = {
    "labels": [st for st, _ in prov_sorted],
    "values": [num(g["provision_strong"].mean(), 2) for _, g in prov_sorted],
}

# 3. морфотипы
morph_chart = {"labels": [], "values": []}
if "morphotype" in results.columns:
    vc = results["morphotype"].astype(str).value_counts()
    morph_chart["labels"] = list(vc.index)
    morph_chart["values"] = [int(v) for v in vc.values]

# 4. распределение населения
pop_hist = {"labels": [], "values": []}
if "population" in results.columns:
    pop = results["population"].dropna()
    pop = pop[pop > 0]
    if len(pop):
        edges = np.histogram_bin_edges(pop, bins=min(8, max(3, len(pop))))
        counts, _ = np.histogram(pop, bins=edges)
        pop_hist["labels"] = [f"{int(edges[i])}–{int(edges[i+1])}" for i in range(len(counts))]
        pop_hist["values"] = [int(c) for c in counts]

# 5. плотность: FSI / GSI
dens_chart = {
    "labels": ["FSI", "GSI"],
    "values": [num(results["fsi"].mean()) if "fsi" in results.columns else None,
               num(results["gsi"].mean()) if "gsi" in results.columns else None],
}

# таблицы
def df_to_html(df, caption):
    if df is None or len(df) == 0:
        return ""
    return (f"<h3>{caption}</h3>" +
            df.to_html(classes="table", border=0, float_format=lambda x: f"{x:,.2f}"))


tables = []
if summary_df is not None:
    s = summary_df.copy()
    s.columns = ["Значение"]
    tables.append(df_to_html(s, "Сводка по территории"))

cols_top = [c for c in ["population", "время_пешком_мин", "area_accessibility", "fsi"]
            if c in results.columns]
if cols_top:
    top = results.copy()
    if "area_accessibility" in top.columns:
        top = top.sort_values("area_accessibility")
        tables.append(df_to_html(
            top[cols_top].head(10).rename(columns={
                "population": "население",
                "время_пешком_мин": "пешком, мин",
                "area_accessibility": "доступность, мин",
                "fsi": "FSI",
            }),
            "10 самых доступных кварталов (меньше — центральнее)"))

if "population" in results.columns:
    top_pop = results.sort_values("population", ascending=False)
    keep = [c for c in ["population", "время_пешком_мин", "morphotype"] if c in results.columns]
    tables.append(df_to_html(
        top_pop[keep].head(10).rename(columns={
            "population": "население",
            "время_пешком_мин": "пешком, мин",
            "morphotype": "морфотип",
        }),
        "10 самых населённых кварталов"))

# --------------------------------------------------------------- выводы
conclusions = []
if "population" in results.columns:
    total = int(results["population"].sum(skipna=True))
    conclusions.append(f"Оценочное население территории — около <b>{total:,}</b> человек.")
if "время_пешком_мин" in results.columns and "время_авто_мин" in results.columns:
    w = num(results["время_пешком_мин"].mean(), 1)
    d = num(results["время_авто_мин"].mean(), 1)
    conclusions.append(
        f"В среднем квартал удалён от других на <b>{w} мин</b> пешком и на <b>{d} мин</b> на автомобиле. "
        "Автомобиль ожидаемо выигрывает по времени на больших расстояниях.")
if "area_accessibility" in results.columns:
    best = results.loc[results["area_accessibility"].idxmin()]
    worst = results.loc[results["area_accessibility"].idxmax()]
    conclusions.append(
        f"Самый доступный квартал находится в <b>{num(best['area_accessibility'], 1)} мин</b> "
        f"от территории в среднем, самый удалённый — <b>{num(worst['area_accessibility'], 1)} мин</b>.")
if provision:
    avg = np.mean([float(g["provision_strong"].mean()) for g in provision.values()])
    weakest = min(provision.items(), key=lambda kv: float(kv[1]["provision_strong"].mean()))
    conclusions.append(
        f"Средняя обеспеченность сервисами (в пределах нормативной доступности) — "
        f"<b>{avg * 100:.0f}%</b>. Хуже всего обеспечен сервис «{weakest[0]}» "
        f"({float(weakest[1]['provision_strong'].mean()) * 100:.0f}%).")
if "morphotype" in results.columns:
    vc = results["morphotype"].astype(str).value_counts()
    if len(vc):
        conclusions.append(
            f"Самый распространённый морфотип — <b>{vc.index[0]}</b> "
            f"({int(vc.iloc[0])} кварталов).")
if "land_use" in results.columns:
    vc = results["land_use"].astype(str).value_counts()
    if len(vc):
        conclusions.append(
            f"Преобладающая функция территории — <b>{vc.index[0]}</b> "
            f"({int(vc.iloc[0])} кварталов).")

conclusions_html = "".join(f"<li>{c}</li>" for c in conclusions) or "<li>Недостаточно данных.</li>"


# --------------------------------------------------------------- HTML
kpi_html = "".join(
    f'<div class="kpi"><div class="kpi-value">{v}</div><div class="kpi-label">{k}</div></div>'
    for k, v in kpi
)

charts_js = json.dumps({
    "time": time_chart, "prov": prov_chart, "morph": morph_chart,
    "pop": pop_hist, "dens": dens_chart,
}, ensure_ascii=False)

iframe = html_lib.escape(map_html, quote=True)
prov_iframe = html_lib.escape(provision_html, quote=True) if provision_html else None

prov_card = ""
if prov_iframe:
    prov_card = f"""
  <div class="card">
    <h2>Обеспеченность сервисами</h2>
    <p style="color:#5b6b7a;font-size:14px;margin-top:-6px">
      Отдельная карта: выберите сервис в списке в правом верхнем углу.
      Шкала общая для всех сервисов: 0 — нет доступа в пределах норматива,
      1 — норматив выполнен.</p>
    <iframe srcdoc="{prov_iframe}"></iframe>
  </div>
"""

page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Покровское — дашборд BlocksNet</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root {{ --bg:#f5f6f8; --card:#fff; --line:#e3e6ea; --accent:#2f6f9f; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
         background: var(--bg); color:#1c2733; }}
  header {{ background: linear-gradient(135deg,#2f6f9f,#1f4e73); color:#fff;
            padding:26px 32px; }}
  header h1 {{ margin:0 0 6px; font-size:26px; }}
  header p {{ margin:0; opacity:.9; }}
  main {{ max-width:1200px; margin:0 auto; padding:24px 20px 60px; }}
  .kpis {{ display:flex; flex-wrap:wrap; gap:14px; margin-bottom:22px; }}
  .kpi {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
          padding:14px 18px; min-width:170px; flex:1; box-shadow:0 1px 3px rgba(0,0,0,.05); }}
  .kpi-value {{ font-size:26px; font-weight:700; color:var(--accent); }}
  .kpi-label {{ font-size:13px; color:#5b6b7a; margin-top:4px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
           padding:18px 20px; margin-bottom:22px; box-shadow:0 1px 3px rgba(0,0,0,.05); }}
  .card h2 {{ margin:0 0 14px; font-size:19px; }}
  .card h3 {{ margin:18px 0 8px; font-size:15px; color:#33475b; }}
  .charts {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:22px; }}
  iframe {{ width:100%; height:640px; border:1px solid var(--line); border-radius:12px; }}
  table.table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  table.table th, table.table td {{ border-bottom:1px solid var(--line); padding:7px 8px;
                                    text-align:left; }}
  table.table th {{ background:#f0f3f7; }}
  table.table tbody tr:nth-child(even) {{ background:#fafbfc; }}
  ul.concl {{ margin:8px 0 0; padding-left:20px; }}
  ul.concl li {{ margin:7px 0; }}
  footer {{ text-align:center; color:#7a8896; font-size:12px; padding:20px; }}
</style>
</head>
<body>
<header>
  <h1>Покровское — анализ территории</h1>
  <p>Интерактивная карта и показатели, рассчитанные библиотекой BlocksNet 1.0.0a9</p>
</header>
<main>
  <div class="kpis">{kpi_html}</div>

  <div class="card">
    <h2>Карта кварталов</h2>
    <p style="color:#5b6b7a;font-size:14px;margin-top:-6px">
      Переключайте слои в правом верхнем углу карты. Наводите курсор на квартал,
      чтобы увидеть значение показателя.</p>
    <iframe srcdoc="{iframe}"></iframe>
  </div>
{prov_card}

  <div class="card">
    <h2>Графики</h2>
    <div class="charts">
      <div><canvas id="chartTime" height="200"></canvas></div>
      <div><canvas id="chartProv" height="200"></canvas></div>
      <div><canvas id="chartDens" height="200"></canvas></div>
      <div><canvas id="chartPop" height="200"></canvas></div>
      <div><canvas id="chartMorph" height="200"></canvas></div>
    </div>
  </div>

  <div class="card">
    <h2>Таблицы</h2>
    {"".join(tables) or "<p>Нет данных для таблиц.</p>"}
  </div>

  <div class="card">
    <h2>Выводы</h2>
    <ul class="concl">{conclusions_html}</ul>
  </div>
</main>
<footer>Сгенерировано examples/make_dashboard.py · данные: examples/data/pokrovskoe</footer>
<script>
const DATA = {charts_js};

const opts = {{
  responsive: true,
  plugins: {{ legend: {{ display: false }} }},
}};

function bar(id, cfg, title, horizontal) {{
  const ctx = document.getElementById(id);
  if (!ctx) return;
  ctx.parentElement.insertAdjacentHTML('beforebegin',
    '<h3>' + title + '</h3>');
  new Chart(ctx, {{
    type: 'bar',
    data: cfg,
    options: Object.assign({{}},
      opts,
      horizontal ? {{ indexAxis: 'y' }} : {{}},
      {{ plugins: {{ legend: {{ display: false }},
                     title: {{ display: false }} }} }}),
  }});
}}

const BLUE = '#2f6f9f', ORANGE = '#f28e2b', GREEN = '#59a14f';

bar('chartTime', {{
  labels: DATA.time.labels,
  datasets: [{{ label: 'Средн. время, мин', data: DATA.time.values,
               backgroundColor: [BLUE, ORANGE] }}],
}}, 'Среднее время в пути между кварталами, мин');

bar('chartProv', {{
  labels: DATA.prov.labels,
  datasets: [{{ label: 'Обеспеченность', data: DATA.prov.values,
               backgroundColor: GREEN }}],
}}, 'Обеспеченность сервисами (0–1, по пешей доступности)', true);

bar('chartDens', {{
  labels: DATA.dens.labels,
  datasets: [{{ label: 'Значение', data: DATA.dens.values,
               backgroundColor: [BLUE, ORANGE] }}],
}}, 'Средние показатели плотности');

bar('chartPop', {{
  labels: DATA.pop.labels,
  datasets: [{{ label: 'Кварталов', data: DATA.pop.values,
               backgroundColor: BLUE }}],
}}, 'Распределение кварталов по населению, чел.');

bar('chartMorph', {{
  labels: DATA.morph.labels,
  datasets: [{{ label: 'Кварталов', data: DATA.morph.values,
               backgroundColor: ORANGE }}],
}}, 'Морфотипы: сколько кварталов каждого типа');
</script>
</body>
</html>
"""

OUT.write_text(page, encoding="utf-8")
print("Готово:", OUT)
print("Размер, КБ:", round(OUT.stat().st_size / 1024))
