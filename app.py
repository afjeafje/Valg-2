import os
import requests
import pandas as pd
import streamlit as st
from datetime import datetime
from urllib.parse import urljoin

BASE = os.environ.get("VALGRESULTAT_BASE", "https://valgresultat.no/api/")
HEADERS = {"User-Agent": "valgresultat-streamlit/1.0"}
MIN_INTERVAL_SECONDS = 30

st.set_page_config(page_title="Valgresultat — kommuner", layout="wide")
st.title("📊 Valgresultat — kommuneresultater")

cols = st.columns([1, 1, 1, 2])
year = cols[0].selectbox("År", ["2021", "2025"], index=0)
valtype = cols[1].selectbox("Valgtype", ["st", "fy", "kv"], index=0)

interval_min = cols[2].number_input("Polling interval (min)", min_value=0.5, max_value=60.0, value=2.0, step=0.5)
interval_seconds = max(int(interval_min * 60), MIN_INTERVAL_SECONDS)

def get_json(path: str):
    url = urljoin(BASE, path.lstrip("/"))
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()

def list_children(path: str):
    data = get_json(path)
    children = []
    if isinstance(data, dict) and "underliggende" in data:
        for c in data["underliggende"]:
            if c.get("href"):
                children.append(c["href"])
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("href"):
                children.append(item["href"])
    return children

@st.cache_data(ttl=300)
def fetch_kommune_results(year: str, valtype: str):
    rows = []
    root_path = f"{year}/{valtype}"
    fylker = list_children(root_path)
    for fylke_path in fylker:
        fylke_id = fylke_path.strip("/").split("/")[-1]
        kommuner = list_children(fylke_path)
        for kommune_path in kommuner:
            kommune_id = kommune_path.strip("/").split("/")[-1]
            data = get_json(kommune_path)
            partis = data.get("partier") or []
            for parti in partis:
                rows.append({
                    "timestamp_utc": datetime.utcnow().isoformat(),
                    "aar": year,
                    "valtype": valtype,
                    "fylke_id": fylke_id,
                    "kommune_id": kommune_id,
                    "kommune_navn": data.get("navn"),
                    "partikode": parti.get("partikode") or parti.get("kode"),
                    "partinavn": parti.get("partinavn") or parti.get("navn"),
                    "stemmer": (parti.get("stemmer") or {}).get("totalt"),
                    "prosent": (parti.get("prosent") or {}).get("totalt"),
                })
    df = pd.DataFrame(rows)
    return df

if st.button("Hent data nå"):
    with st.spinner("Henter kommuneresultater..."):
        try:
            df = fetch_kommune_results(year, valtype)
            st.success(f"Hentet {len(df)} rader")
            st.dataframe(df)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Last ned CSV", csv, file_name=f"valg_{year}_{valtype}.csv", mime="text/csv")
        except Exception as e:
            st.error(f"Feil: {e}")
