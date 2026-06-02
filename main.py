import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
import uvicorn
from datetime import datetime, timezone, timedelta
import os
import pickle

# ==========================================
# 1. AYARLAR
# ==========================================
app = FastAPI(title="Akıllı Ev NILM - Back-End")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

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
# 2. CNN-LSTM MODEL YUKLEME
# ==========================================
MODEL_HAZIR = False
model  = None
scaler = None
le     = None

try:
    import tensorflow as tf
    model = tf.keras.models.load_model("nilm_model.keras")
    with open("scaler.pkl", "rb") as f:
        scaler = pickle.load(f)
    with open("label_encoder.pkl", "rb") as f:
        le = pickle.load(f)
    MODEL_HAZIR = True
    print("CNN-LSTM modeli yuklendi")
except Exception as e:
    print(f"Model yuklenemedi, kural tabanli mod aktif: {e}")


# ==========================================
# 3. YARDIMCI FONKSIYONLAR
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

    if MODEL_HAZIR and len(guc_verileri) >= 30:
        try:
            pencere = np.array([
                [guc_verileri[i], pf_verileri[i] if i < len(pf_verileri) else 1.0]
                for i in range(-30, 0)
            ])
            pencere_scaled = scaler.transform(pencere).reshape(1, 30, 2)
            tahmin = model.predict(pencere_scaled, verbose=0)
            return le.inverse_transform([np.argmax(tahmin)])[0]
        except Exception as e:
            print(f"Model tahmin hatasi: {e}")

    aktif = []

    if son_watt >= 5:
        aktif.append("Buzdolabi")

    if son_watt > 1500:
        aktif = ["Camasir Makinesi (Isitma)", "Buzdolabi"]
    elif 300 <= son_watt <= 1500 and son_pf < 0.82:
        if "Buzdolabi" not in aktif:
            aktif.append("Buzdolabi")
        aktif.append("Camasir Makinesi")
    elif son_watt > 1000 and son_pf > 0.90:
        aktif.append("Firin")
    elif son_watt > 800 and son_pf > 0.90:
        aktif.append("Sac Kurutma")
    elif son_watt > 600 and son_pf > 0.90:
        aktif.append("Utu")
    elif son_watt < 200 and son_pf < 0.75:
        aktif = ["Televizyon", "Buzdolabi"]

    if not aktif:
        return "Bosta"

    return " + ".join(aktif)

def kwh_bilgi_hesapla(client: InfluxDBClient) -> dict:
    """
    Son 15 gunluk ana sayac verisinden:
    - gercek_kwh   : toplam olculen kWh
    - gunluk_ort   : gunluk ortalama kWh
    - projeksiyon  : 30 gune projeksiyon kWh
    """
    query_api = client.query_api()
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -15d)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> filter(fn: (r) => r["cihaz"] == "ana_sayac")
        |> filter(fn: (r) => r["ev"] == "ev1")
        |> sort(columns: ["_time"])
    '''
    bos = {"gercek_kwh": 0.0, "gunluk_ort": 0.0, "projeksiyon": 0.0}
    try:
        result   = query_api.query(org=INFLUX_ORG, query=query)
        kayitlar = []
        for table in result:
            for record in table.records:
                kayitlar.append((record.get_time(), record.get_value() or 0.0))

        if len(kayitlar) < 2:
            return bos

        toplam_wh = 0.0
        for i in range(1, len(kayitlar)):
            t0, w0 = kayitlar[i - 1]
            t1, w1 = kayitlar[i]
            sure_saat = (t1 - t0).total_seconds() / 3600.0
            if sure_saat > (10 / 60):
                continue
            ort_watt = max((w0 + w1) / 2.0, 0.0)
            toplam_wh += ort_watt * sure_saat

        gercek_kwh = round(max(toplam_wh, 0.0) / 1000.0, 2)

        sure_gun = (kayitlar[-1][0] - kayitlar[0][0]).total_seconds() / 86400.0
        if sure_gun < 0.1:
            return {"gercek_kwh": gercek_kwh, "gunluk_ort": 0.0, "projeksiyon": 0.0}

        gunluk_ort  = round(gercek_kwh / sure_gun, 2)
        projeksiyon = round(gunluk_ort * 30, 2)

        return {
            "gercek_kwh": gercek_kwh,
            "gunluk_ort": gunluk_ort,
            "projeksiyon": projeksiyon,
        }
    except Exception as e:
        print(f"KWH HESAP HATASI: {e}")
        return bos

def son_watt_getir(client: InfluxDBClient, cihaz_tag: str) -> float:
    query_api = client.query_api()
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -2m)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> filter(fn: (r) => r["cihaz"] == "{cihaz_tag}")
        |> mean()
    '''
    try:
        result = query_api.query(org=INFLUX_ORG, query=query)
        for table in result:
            for record in table.records:
                return round(record.get_value() or 0.0, 1)
        return 0.0
    except Exception as e:
        print(f"WATT GETIR HATASI ({cihaz_tag}): {e}")
        return 0.0

def seyyar_watt_getir(client: InfluxDBClient) -> float:
    query_api = client.query_api()
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -2m)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> filter(fn: (r) => r["cihaz"] != "ana_sayac")
        |> filter(fn: (r) => r["cihaz"] != "buzdolabi")
        |> mean()
    '''
    try:
        result = query_api.query(org=INFLUX_ORG, query=query)
        for table in result:
            for record in table.records:
                return round(record.get_value() or 0.0, 1)
        return 0.0
    except Exception as e:
        print(f"SEYYAR WATT HATASI: {e}")
        return 0.0


# ==========================================
# 4. EV DURUMU ENDPOINTI
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
        |> sort(columns: ["_time"])
    '''
    try:
        results       = query_api.query(org=INFLUX_ORG, query=query)
        guc_noktalari = []
        pf_noktalari  = []
        anlik_watt    = 0.0
        is_alive      = False

        for table in results:
            for record in table.records:
                val   = record.get_value() or 0.0
                field = record.get_field()
                if field == "guc":
                    guc_noktalari.append(val)
                    anlik_watt = val
                elif field == "guc_faktoru":
                    pf_noktalari.append(val)
                gecen_sure = (datetime.now(timezone.utc) - record.get_time()).total_seconds()
                if gecen_sure < 120:
                    is_alive = True

        aktif_cihaz = tahmin_et(guc_noktalari, pf_noktalari)
        kwh_bilgi   = kwh_bilgi_hesapla(client)

        gunluk_ort  = kwh_bilgi["gunluk_ort"]
        projeksiyon = kwh_bilgi["projeksiyon"]
        fatura_tl   = _fatura_hesapla_kwh(projeksiyon)

        return {
            "durum":             "Basarili" if is_alive else "Cevrimdisi",
            "anlik_toplam_watt": f"{round(anlik_watt, 1)} W",
            "aktif_cihaz":       aktif_cihaz,
            "gunluk_ort_kwh":    f"{gunluk_ort} kWh/gun",
            "projeksiyon_kwh":   f"{projeksiyon} kWh",
            "tahmini_fatura":    f"{fatura_tl} TL",
        }
    except Exception as e:
        return {"durum": "Hata", "mesaj": str(e)}
    finally:
        client.close()


# ==========================================
# 5. CIHAZ DETAYLARI ENDPOINTI
# ==========================================
@app.api_route("/cihaz-detaylari", methods=["GET", "HEAD"])
def get_cihaz_detaylari():
    cihazlar = [
        {"ad": "Ana Sayac (ESP32)", "tag": "ana_sayac", "ikon": "electric_meter"},
        {"ad": "Buzdolabi",         "tag": "buzdolabi", "ikon": "kitchen"},
    ]
    client = get_influx_client()
    try:
        sonuclar = []
        for cihaz in cihazlar:
            watt       = son_watt_getir(client, cihaz["tag"])
            saatlik_tl = watt_to_saatlik_tl(watt)
            durum      = "Aktif" if watt > 5 else "Bekleme"
            sonuclar.append({
                "cihaz":           cihaz["ad"],
                "ikon":            cihaz["ikon"],
                "anlik_watt":      f"{watt} W",
                "saatlik_maliyet": f"{saatlik_tl} TL/saat",
                "durum":           durum,
            })
        seyyar_watt = seyyar_watt_getir(client)
        seyyar_tl   = watt_to_saatlik_tl(seyyar_watt)
        sonuclar.append({
            "cihaz":           "Seyyar Priz",
            "ikon":            "power",
            "anlik_watt":      f"{seyyar_watt} W",
            "saatlik_maliyet": f"{seyyar_tl} TL/saat",
            "durum":           "Aktif" if seyyar_watt > 5 else "Bekleme",
        })
        return sonuclar
    except Exception as e:
        return [{"cihaz": "Hata", "mesaj": str(e)}]
    finally:
        client.close()


# ==========================================
# 6. ENERJI GECMISI — PASTA GRAFIK
# kWh bazli dagilim dondurur
# ==========================================
@app.api_route("/enerji-gecmisi", methods=["GET", "HEAD"])
def get_enerji_gecmisi():
    client    = get_influx_client()
    query_api = client.query_api()
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -15d)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> filter(fn: (r) => r["ev"] == "ev1")
        |> filter(fn: (r) =>
               r["cihaz"] == "ana_sayac" or
               r["cihaz"] == "buzdolabi" or
               r["cihaz"] == "televizyon"
        )
        |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
    '''
    try:
        result      = query_api.query(org=INFLUX_ORG, query=query)
        cihaz_wh    = {"ana_sayac": 0.0, "buzdolabi": 0.0, "televizyon": 0.0}
        cihaz_sayac = {"ana_sayac": 0,   "buzdolabi": 0,   "televizyon": 0}

        for table in result:
            for record in table.records:
                tag   = str(record.values.get("cihaz") or "").lower().strip()
                value = record.get_value() or 0.0
                if tag in cihaz_wh:
                    cihaz_wh[tag]    += value
                    cihaz_sayac[tag] += 1

        def ort_kwh(tag):
            if cihaz_sayac[tag] == 0:
                return 0.0
            return round(cihaz_wh[tag] / 1000.0, 2)

        kwh_ana   = ort_kwh("ana_sayac")
        kwh_buz   = ort_kwh("buzdolabi")
        kwh_tv    = ort_kwh("televizyon")
        kwh_diger = max(0.0, round(kwh_ana - kwh_buz - kwh_tv, 2))
        toplam    = kwh_ana if kwh_ana > 0 else (kwh_buz + kwh_tv + kwh_diger)

        def yuzde(kwh):
            if toplam == 0:
                return 0.0
            return round(kwh / toplam * 100, 1)

        return {
            "pasta": [
                {"cihaz": "Buzdolabi",  "kwh": kwh_buz,   "yuzde": yuzde(kwh_buz)},
                {"cihaz": "Televizyon", "kwh": kwh_tv,    "yuzde": yuzde(kwh_tv)},
                {"cihaz": "Diger",      "kwh": kwh_diger, "yuzde": yuzde(kwh_diger)},
            ],
            "toplam_kwh": kwh_ana,
            "sure_gun":   15,
        }
    except Exception as e:
        print(f"ENERJI GECMISI HATASI: {e}")
        return {"pasta": [], "toplam_kwh": 0.0, "sure_gun": 15}
    finally:
        client.close()


# ==========================================
# 7. GRAFIK GECMISI — CIZGI GRAFIK
# Flutter cizgi grafik sayfasi bu endpoint'i kullanir
# ==========================================
@app.api_route("/grafik-gecmisi", methods=["GET", "HEAD"])
def get_grafik_gecmisi(saat: int = 1):
    client    = get_influx_client()
    query_api = client.query_api()

    if saat <= 1:
        pencere = "1m"
    elif saat <= 24:
        pencere = "5m"
    else:
        pencere = "1h"

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
               r["cihaz"] == "televizyon"
        )
        |> aggregateWindow(every: {pencere}, fn: mean, createEmpty: true)
        |> filter(fn: (r) => r["_value"] < 3000)
        |> fill(value: 0.0)
    '''

    TURKEY_TZ = timezone(timedelta(hours=3))

    try:
        result   = query_api.query(org=INFLUX_ORG, query=query)
        time_map = {}

        for table in result:
            for record in table.records:
                time  = record.get_time().astimezone(TURKEY_TZ).strftime("%Y-%m-%dT%H:%M:%S")
                value = record.get_value() or 0.0
                tag   = str(record.values.get("cihaz") or "").lower().strip()

                if time not in time_map:
                    time_map[time] = {"ana_sayac": 0.0, "buzdolabi": 0.0, "seyyar_priz": 0.0}

                if tag == "ana_sayac":
                    time_map[time]["ana_sayac"]   = round(value, 1)
                elif tag == "buzdolabi":
                    time_map[time]["buzdolabi"]   = round(value, 1)
                elif tag == "televizyon":
                    time_map[time]["seyyar_priz"] = round(value, 1)

        final_list = [
            {
                "zaman":       t,
                "esp32_ana":   d["ana_sayac"],
                "buzdolabi":   d["buzdolabi"],
                "seyyar_priz": d["seyyar_priz"],
            }
            for t, d in time_map.items()
        ]
        final_list.sort(key=lambda x: x["zaman"])
        return final_list

    except Exception as e:
        print(f"GRAFIK HATASI: {e}")
        return []
    finally:
        client.close()


# ==========================================
# 8. SAGLIK KONTROLU
# ==========================================
@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"mesaj": "Akilli Ev NILM API calisiyor."}

@app.api_route("/ping", methods=["GET", "HEAD"])
def ping():
    return {"status": "ok"}


# ==========================================
# 9. SUNUCU
# ==========================================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
