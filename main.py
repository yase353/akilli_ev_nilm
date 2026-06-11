import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
import uvicorn
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
import os

# ==========================================
# 1. AYARLAR
# ==========================================
INFLUX_URL    = os.environ.get("INFLUX_URL",    "https://eu-central-1-1.aws.cloud2.influxdata.com")
INFLUX_TOKEN  = os.environ.get("INFLUX_TOKEN",  "")
INFLUX_ORG    = os.environ.get("INFLUX_ORG",    "2a22ab52153e142d")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "tez_verileri")

AKTIF_DUSUK  = 2.92
AKTIF_YUKSEK = 4.38
DAGITIM      = 1.84
KDV_ORAN     = 0.01
BTV_ORAN     = 0.05

def get_influx_client():
    return InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)


# ==========================================
# 2. CNN-LSTM MODEL
# ==========================================
MODEL_HAZIR = False
model = scaler = le = None
print("Kural tabanli mod aktif")


# ==========================================
# 3. CACHE TANIMI
# kwh     : 60  saniyede bir guncellenir
# enerji  : 300 saniyede bir guncellenir (5dk — pasta grafik)
# cihaz   : 30  saniyede bir guncellenir
# ==========================================
_kwh_cache    = {"veri": None, "son": None}
_enerji_cache = {"veri": None, "son": None}
_cihaz_cache  = {"veri": None, "son": None}

def _cache_gecerli(cache: dict, sure_sn: int) -> bool:
    return (
        cache["veri"] is not None and
        cache["son"]  is not None and
        (datetime.now(timezone.utc) - cache["son"]).total_seconds() < sure_sn
    )

def _cache_guncelle(cache: dict, veri):
    cache["veri"] = veri
    cache["son"]  = datetime.now(timezone.utc)


# ==========================================
# 4. STARTUP — cache'i on
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        client = get_influx_client()
        _cache_guncelle(_kwh_cache,   kwh_bilgi_hesapla(client))
        _cache_guncelle(_enerji_cache, enerji_gecmisi_hesapla(client))
        _cache_guncelle(_cihaz_cache,  cihaz_detaylari_hesapla(client))
        client.close()
        print("Startup cache dolduruldu")
    except Exception as e:
        print(f"Startup cache hatasi: {e}")
    yield


# ==========================================
# 5. APP
# ==========================================
app = FastAPI(title="Akilli Ev NILM - Back-End", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


# ==========================================
# 6. YARDIMCI FONKSIYONLAR
# ==========================================
def _fatura_hesapla_kwh(kwh: float) -> float:
    if kwh <= 0:
        return 0.0
    aktif   = min(kwh, 240) * AKTIF_DUSUK + max(0.0, kwh - 240) * AKTIF_YUKSEK
    dagitim = kwh * DAGITIM
    ara     = aktif + dagitim
    btv     = aktif * BTV_ORAN
    kdv     = (ara + btv) * KDV_ORAN
    return round(ara + btv + kdv, 2)

def watt_to_saatlik_tl(watt: float) -> float:
    kwh     = watt / 1000.0
    aktif   = kwh * AKTIF_DUSUK
    dagitim = kwh * DAGITIM
    ara     = aktif + dagitim
    btv     = aktif * BTV_ORAN
    kdv     = (ara + btv) * KDV_ORAN
    return round(ara + btv + kdv, 4)

def tahmin_et(guc_verileri: list, pf_verileri: list = []) -> str:
    if not guc_verileri:
        return "Veri Bekleniyor..."
    son_watt = guc_verileri[-1]
    son_pf   = pf_verileri[-1] if pf_verileri else 1.0
    aktif    = []
    if son_watt >= 5:
        aktif.append("Buzdolabi")

    # Cihaz watt araliklari (Hucre 16 sabit degerlerine gore):
    # Utu       ~1200W (1280-1500W gurultuyle)
    # Sac Kurutma ~1650W (1400-2150W gurultuyle)
    # Firin     ~1800W (1400-2150W gurultuyle, sac kurutma ile cakisir)
    # Camasir Isitma ~2100W (1800W+)
    # Supurge   ~1100W

    if son_watt > 1900:
        aktif = ["Camasir Makinesi (Isitma)", "Buzdolabi"]
    elif 300 <= son_watt <= 1900 and son_pf < 0.82:
        if "Buzdolabi" not in aktif:
            aktif.append("Buzdolabi")
        aktif.append("Camasir Makinesi")
    elif 1250 <= son_watt <= 1900 and son_pf > 0.90:
        # Firin ve Sac Kurutma bu aralikta cakisiyor, ayirt edilemiyor
        aktif.append("Firin/Sac Kurutma")
    elif 1000 <= son_watt < 1250 and son_pf > 0.90:
        aktif.append("Utu")
    elif 800 <= son_watt < 1250 and son_pf > 0.90:
        aktif.append("Supurge")

    if son_pf < 0.78 and son_watt < 400 and son_watt > 50:
        if "Televizyon" not in aktif:
            aktif.append("Televizyon")
    return " + ".join(aktif) if aktif else "Bosta"

def kwh_bilgi_hesapla(client: InfluxDBClient) -> dict:
    """
    InfluxDB'de 1 dakikalik aggregateWindow ile veri seyreltilir.
    Tek donguyle toplam Wh (her 1dk noktasi watt/60 Wh temsil eder)
    ve kayit sayisi (= toplam dakika) hesaplanir.

    gunluk_ort, "su anki ortalama tuketim hizi 24 saat boyunca devam
    etseydi ne kadar kWh tuketilirdi" sorusuna cevap verir:
        ortalama_watt = toplam_wh / toplam_dakika
        gunluk_kwh    = ortalama_watt * 24 / 1000

    Bu yaklasim, veri penceresinin uzunlugundan (1 saatlik veri de,
    15 gunluk veri de) bagimsiz olarak dogru gunluk projeksiyon verir
    -- onceki versiyondaki "kisa pencere -> sisirilmis gunluk_ort"
    sorununu ortadan kaldirir.

    query_stream() ile sonuc satir satir okunur, belleğe yigilmaz.
    """
    bos = {"gercek_kwh": 0.0, "gunluk_ort": 0.0, "projeksiyon": 0.0}
    try:
        agg_query = f'''
            from(bucket: "{INFLUX_BUCKET}")
            |> range(start: -1d)
            |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
            |> filter(fn: (r) => r["_field"] == "guc")
            |> filter(fn: (r) => r["cihaz"] == "ana_sayac")
            |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
        '''
        toplam_wh   = 0.0
        toplam_dk   = 0
        for record in client.query_api().query_stream(org=INFLUX_ORG, query=agg_query):
            val = record.get_value() or 0.0
            toplam_wh += val / 60.0  # 1 dakikalik dilim -> Wh
            toplam_dk += 1

        if toplam_dk == 0 or toplam_wh <= 0:
            return bos

        # Son 15 gunde toplam tuketilen gercek enerji (15 gunluk pencere)
        gercek_query = f'''
            from(bucket: "{INFLUX_BUCKET}")
            |> range(start: -15d)
            |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
            |> filter(fn: (r) => r["_field"] == "guc")
            |> filter(fn: (r) => r["cihaz"] == "ana_sayac")
            |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
        '''
        toplam_wh_15g = 0.0
        for record in client.query_api().query_stream(org=INFLUX_ORG, query=gercek_query):
            toplam_wh_15g += (record.get_value() or 0.0) / 60.0

        gercek_kwh = round(toplam_wh_15g / 1000.0, 2)

        # Ortalama watt (son 1 gunluk pencereden) -> 24 saatlik gunluk projeksiyon
        ortalama_watt = toplam_wh / toplam_dk * 60.0  # Wh/dk -> W
        gunluk_ort    = round(ortalama_watt * 24 / 1000.0, 2)
        projeksiyon   = round(gunluk_ort * 30, 2)

        return {"gercek_kwh": gercek_kwh, "gunluk_ort": gunluk_ort, "projeksiyon": projeksiyon}
    except Exception as e:
        print(f"KWH HATASI: {e}")
        return bos

def enerji_gecmisi_hesapla(client: InfluxDBClient) -> dict:
    try:
        query = f'''
            from(bucket: "{INFLUX_BUCKET}")
            |> range(start: -3d)
            |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
            |> filter(fn: (r) => r["_field"] == "guc")
            |> filter(fn: (r) => r["ev"] == "ev1")
            |> filter(fn: (r) =>
                   r["cihaz"] == "ana_sayac" or
                   r["cihaz"] == "buzdolabi" or
                   r["cihaz"] == "televizyon")
            |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
        '''
        cihaz_wh    = {"ana_sayac": 0.0, "buzdolabi": 0.0, "televizyon": 0.0}
        cihaz_sayac = {"ana_sayac": 0,   "buzdolabi": 0,   "televizyon": 0}
        for record in client.query_api().query_stream(org=INFLUX_ORG, query=query):
            tag = str(record.values.get("cihaz") or "").lower().strip()
            if tag in cihaz_wh:
                cihaz_wh[tag]    += record.get_value() or 0.0
                cihaz_sayac[tag] += 1

        def ort_kwh(tag):
            return round(cihaz_wh[tag]/1000.0, 2) if cihaz_sayac[tag] > 0 else 0.0

        kwh_ana   = ort_kwh("ana_sayac")
        kwh_buz   = ort_kwh("buzdolabi")
        kwh_tv    = ort_kwh("televizyon")
        kwh_diger = max(0.0, round(kwh_ana - kwh_buz - kwh_tv, 2))
        toplam    = kwh_ana or (kwh_buz + kwh_tv + kwh_diger)

        def yuzde(k): return round(k/toplam*100, 1) if toplam > 0 else 0.0

        return {
            "pasta": [
                {"cihaz": "Buzdolabi",  "kwh": kwh_buz,   "yuzde": yuzde(kwh_buz)},
                {"cihaz": "Televizyon", "kwh": kwh_tv,    "yuzde": yuzde(kwh_tv)},
                {"cihaz": "Diger",      "kwh": kwh_diger, "yuzde": yuzde(kwh_diger)},
            ],
            "toplam_kwh": kwh_ana, "sure_gun": 3,
        }
    except Exception as e:
        print(f"ENERJI HATASI: {e}")
        return {"pasta": [], "toplam_kwh": 0.0, "sure_gun": 3}

CIHAZ_GORUNUM = {
    "ana_sayac":        ("Ana Sayac (ESP32)", "electric_meter"),
    "buzdolabi":        ("Buzdolabi",         "kitchen"),
    "televizyon":       ("Televizyon",        "tv"),
    "camasir_makinesi": ("Camasir Makinesi",  "local_laundry_service"),
    "firin":            ("Firin",             "microwave"),
    "utu":              ("Utu",               "iron"),
    "sac_kurutma":      ("Sac Kurutma",       "dry"),
    "supurge":          ("Supurge",           "cleaning_services"),
}

def cihaz_detaylari_hesapla(client: InfluxDBClient) -> list:
    """
    Son 1 dakika icinde InfluxDB'ye yazilmis TUM cihaz tag'lerini ceker.
    Hucre 16'nin o an yazdigi cihazlar (ana_sayac, buzdolabi ve aktif
    olan diger cihazlar) birebir burada da gorunur.
    """
    try:
        q = f'''
            from(bucket: "{INFLUX_BUCKET}")
            |> range(start: -20s)
            |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
            |> filter(fn: (r) => r["_field"] == "guc")
            |> group(columns: ["cihaz"])
            |> last()
        '''
        sonuclar = []
        for record in client.query_api().query_stream(org=INFLUX_ORG, query=q):
            tag = str(record.values.get("cihaz") or "").lower().strip()
            if not tag:
                continue
            w = round(record.get_value() or 0.0, 1)
            ad, ikon = CIHAZ_GORUNUM.get(tag, (tag.replace("_", " ").title(), "power"))
            sonuclar.append({
                "cihaz": ad, "ikon": ikon,
                "anlik_watt":      f"{w} W",
                "saatlik_maliyet": f"{watt_to_saatlik_tl(w)} TL/saat",
                "durum":           "Aktif" if w > 5 else "Bekleme",
            })

        sonuclar.sort(key=lambda x: 0 if x["cihaz"] == "Ana Sayac (ESP32)" else 1)
        return sonuclar
    except Exception as e:
        print(f"CIHAZ DETAY HATASI: {e}")
        return []


# ==========================================
# 7. EV DURUMU
# ==========================================
@app.api_route("/ev-durumu", methods=["GET", "HEAD"])
def get_ev_durumu():
    client    = get_influx_client()
    query_api = client.query_api()
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -5m)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc" or r["_field"] == "guc_faktoru")
        |> filter(fn: (r) => r["cihaz"] == "ana_sayac")
        |> filter(fn: (r) => r["ev"] == "ev1")
        |> sort(columns: ["_time"])
    '''
    try:
        guc_noktalari = []
        pf_noktalari  = []
        anlik_watt    = 0.0
        is_alive      = False
        for record in query_api.query_stream(org=INFLUX_ORG, query=query):
            val   = record.get_value() or 0.0
            field = record.get_field()
            if field == "guc":
                guc_noktalari.append(val)
                anlik_watt = val
            elif field == "guc_faktoru":
                pf_noktalari.append(val)
            if (datetime.now(timezone.utc) - record.get_time()).total_seconds() < 120:
                is_alive = True

        aktif_cihaz = tahmin_et(guc_noktalari, pf_noktalari)

        # 60sn cache
        if not _cache_gecerli(_kwh_cache, 60):
            _cache_guncelle(_kwh_cache, kwh_bilgi_hesapla(client))
        kwh     = _kwh_cache["veri"]
        fatura  = _fatura_hesapla_kwh(kwh["projeksiyon"])

        return {
            "durum":             "Basarili" if is_alive else "Cevrimdisi",
            "anlik_toplam_watt": f"{round(anlik_watt, 1)} W",
            "aktif_cihaz":       aktif_cihaz,
            "gunluk_ort_kwh":    f"{kwh['gunluk_ort']} kWh/gun",
            "projeksiyon_kwh":   f"{kwh['projeksiyon']} kWh",
            "tahmini_fatura":    f"{fatura} TL",
        }
    except Exception as e:
        return {"durum": "Hata", "mesaj": str(e)}
    finally:
        client.close()


# ==========================================
# 8. CIHAZ DETAYLARI — 30sn cache
# ==========================================
@app.api_route("/cihaz-detaylari", methods=["GET", "HEAD"])
def get_cihaz_detaylari():
    if _cache_gecerli(_cihaz_cache, 5):
        return _cihaz_cache["veri"]
    client = get_influx_client()
    try:
        veri = cihaz_detaylari_hesapla(client)
        _cache_guncelle(_cihaz_cache, veri)
        return veri
    except Exception as e:
        return [{"cihaz": "Hata", "mesaj": str(e)}]
    finally:
        client.close()


# ==========================================
# 9. ENERJI GECMISI — 5dk cache
# ==========================================
@app.api_route("/enerji-gecmisi", methods=["GET", "HEAD"])
def get_enerji_gecmisi():
    if _cache_gecerli(_enerji_cache, 300):
        return _enerji_cache["veri"]
    client = get_influx_client()
    try:
        veri = enerji_gecmisi_hesapla(client)
        _cache_guncelle(_enerji_cache, veri)
        return veri
    except Exception as e:
        print(f"ENERJI HATASI: {e}")
        return {"pasta": [], "toplam_kwh": 0.0, "sure_gun": 3}
    finally:
        client.close()


# ==========================================
# 10. GRAFIK GECMISI — CIZGI GRAFIK
# ==========================================
@app.api_route("/grafik-gecmisi", methods=["GET", "HEAD"])
def get_grafik_gecmisi(saat: int = 1):
    client    = get_influx_client()
    query_api = client.query_api()
    pencere   = "1m" if saat <= 1 else ("5m" if saat <= 24 else "1h")
    TURKEY_TZ = timezone(timedelta(hours=3))
    query = f'''
        import "timezone"
        option location = timezone.location(name: "Europe/Istanbul")
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -{saat}h)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> filter(fn: (r) => r["ev"] == "ev1")
        |> filter(fn: (r) =>
               r["cihaz"] == "ana_sayac" or
               r["cihaz"] == "buzdolabi" or
               r["cihaz"] == "televizyon")
        |> aggregateWindow(every: {pencere}, fn: mean, createEmpty: true)
        |> filter(fn: (r) => r["_value"] < 3000)
        |> fill(value: 0.0)
    '''
    try:
        time_map = {}
        for record in query_api.query_stream(org=INFLUX_ORG, query=query):
            t   = record.get_time().astimezone(TURKEY_TZ).strftime("%Y-%m-%dT%H:%M:%S")
            val = record.get_value() or 0.0
            tag = str(record.values.get("cihaz") or "").lower().strip()
            if t not in time_map:
                time_map[t] = {"ana_sayac": 0.0, "buzdolabi": 0.0, "seyyar_priz": 0.0}
            if tag == "ana_sayac":
                time_map[t]["ana_sayac"]   = round(val, 1)
            elif tag == "buzdolabi":
                time_map[t]["buzdolabi"]   = round(val, 1)
            elif tag == "televizyon":
                time_map[t]["seyyar_priz"] = round(val, 1)
        final = sorted(
            [{"zaman": t, "esp32_ana": d["ana_sayac"],
              "buzdolabi": d["buzdolabi"], "seyyar_priz": d["seyyar_priz"]}
             for t, d in time_map.items()],
            key=lambda x: x["zaman"]
        )
        return final
    except Exception as e:
        print(f"GRAFIK HATASI: {e}")
        return []
    finally:
        client.close()


# ==========================================
# 11. SAGLIK
# ==========================================
@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"mesaj": "Akilli Ev NILM API calisiyor."}

@app.api_route("/ping", methods=["GET", "HEAD"])
def ping():
    return {"status": "ok"}


# ==========================================
# 12. SUNUCU
# ==========================================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
