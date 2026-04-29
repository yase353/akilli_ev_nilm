import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
import uvicorn
from datetime import datetime, timezone
import os

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
INFLUX_TOKEN  = os.environ.get("INFLUX_TOKEN",  "Ce_D58Wv76g1kf0Qx9oqIiGZ-CTHIYUIfGnOAHH7bw3UmXie7F6yXfZyn6rlKU-EA0wm0YT7KloeF-ptcYD6bw==")
INFLUX_ORG    = os.environ.get("INFLUX_ORG",    "2a22ab52153e142d")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "tez_verileri")

FIYAT_DUSUK  = 2.07
FIYAT_YUKSEK = 3.10

def get_influx_client():
    return InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)


# ==========================================
# 2. YARDIMCI FONKSİYONLAR
# ==========================================
def watt_to_saatlik_tl(watt: float) -> float:
    kwh_saatlik = watt / 1000.0
    return round(kwh_saatlik * FIYAT_DUSUK, 4)

def tahmin_et(guc_verileri: list, pf_verileri: list = []) -> str:
    if not guc_verileri:
        return "Veri Bekleniyor..."

    son_watt = guc_verileri[-1]
    son_pf   = pf_verileri[-1] if pf_verileri else 1.0

    if son_watt < 15:
        return "Bosta"
    elif son_watt < 500 and son_pf > 0.95:
        return "Utu"
    elif son_watt < 200 and son_pf < 0.85:
        return "Televizyon"
    elif son_watt > 200 and son_pf < 0.80:
        return "Camasir Makinesi"
    else:
        return "Bilinmiyor"

def gercek_aylik_kwh_hesapla(client: InfluxDBClient) -> float:
    query_api = client.query_api()
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -30d)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> filter(fn: (r) => r["cihaz"] == "ana_sayac")
        |> sort(columns: ["_time"])
    '''
    try:
        result = query_api.query(org=INFLUX_ORG, query=query)
        kayitlar = []
        for table in result:
            for record in table.records:
                kayitlar.append((record.get_time(), record.get_value() or 0.0))

        if len(kayitlar) < 2:
            return 0.0

        toplam_wh = 0.0
        for i in range(1, len(kayitlar)):
            t0, w0 = kayitlar[i - 1]
            t1, w1 = kayitlar[i]
            sure_saat = (t1 - t0).total_seconds() / 3600.0
            ort_watt  = (w0 + w1) / 2.0
            toplam_wh += ort_watt * sure_saat

        return round(toplam_wh / 1000.0, 2)
    except Exception as e:
        print(f"FATURA HESAP HATASI: {e}")
        return 0.0

def fatura_hesapla(aylik_kwh: float) -> float:
    ilk_dilim    = min(aylik_kwh, 240) * FIYAT_DUSUK
    ikinci_dilim = max(0.0, aylik_kwh - 240) * FIYAT_YUKSEK
    return round(ilk_dilim + ikinci_dilim, 2)

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


# ==========================================
# 3. EV DURUMU ENDPOINTI
# ==========================================
@app.api_route("/ev-durumu", methods=["GET", "HEAD"])
def get_ev_durumu():
    client = get_influx_client()
    query_api = client.query_api()

    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -1m)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc" or r["_field"] == "guc_faktoru")
        |> filter(fn: (r) => r["cihaz"] == "ana_sayac")
        |> sort(columns: ["_time"])
    '''
    try:
        results = query_api.query(org=INFLUX_ORG, query=query)
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

        aktif_cihaz    = tahmin_et(guc_noktalari, pf_noktalari)
        aylik_kwh      = gercek_aylik_kwh_hesapla(client)
        tahmini_fatura = fatura_hesapla(aylik_kwh)

        return {
            "durum":             "Basarili" if is_alive else "Cevrimdisi",
            "tahmini_fatura":    f"{tahmini_fatura} TL",
            "aylik_tuketim_kwh": f"{aylik_kwh}",
            "anlik_toplam_watt": f"{round(anlik_watt, 1)} W",
            "aktif_cihaz":       aktif_cihaz
        }
    except Exception as e:
        return {"durum": "Hata", "mesaj": str(e)}
    finally:
        client.close()


# ==========================================
# 4. CIHAZ DETAYLARI ENDPOINTI
# ==========================================
@app.api_route("/cihaz-detaylari", methods=["GET", "HEAD"])
def get_cihaz_detaylari():
    cihazlar = [
        {"ad": "Ana Sayac (ESP32)", "tag": "ana_sayac", "ikon": "electric_meter"},
        {"ad": "Buzdolabi",         "tag": "buzdolabi", "ikon": "kitchen"},
        {"ad": "Seyyar Priz",       "tag": "utu",       "ikon": "power"},
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
                "durum":           durum
            })

        return sonuclar
    except Exception as e:
        return [{"cihaz": "Hata", "mesaj": str(e)}]
    finally:
        client.close()


# ==========================================
# 5. ENERJI GECMISI ENDPOINTI
# ==========================================
@app.api_route("/enerji-gecmisi", methods=["GET", "HEAD"])
def get_enerji_gecmisi(saat: int = 1):
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
        |> aggregateWindow(every: {pencere}, fn: mean, createEmpty: true)
        |> fill(value: 0.0)
    '''

    try:
        result   = query_api.query(org=INFLUX_ORG, query=query)
        time_map = {}

        for table in result:
            for record in table.records:
                time  = record.get_time().isoformat()
                value = record.get_value() or 0.0
                tag   = str(record.values.get("cihaz") or "").lower().strip()

                if time not in time_map:
                    time_map[time] = {
                        "ana_sayac":   0.0,
                        "buzdolabi":   0.0,
                        "utu":         0.0,
                        "seyyar_priz": 0.0
                    }

                if "ana" in tag or "esp" in tag:
                    time_map[time]["ana_sayac"]   = round(value, 1)
                elif "buz" in tag or "dolap" in tag:
                    time_map[time]["buzdolabi"]   = round(value, 1)
                elif "utu" in tag:
                    time_map[time]["utu"]         = round(value, 1)
                elif any(x in tag for x in ["seyyar", "camasir", "priz", "tv", "televizyon"]):
                    time_map[time]["seyyar_priz"] = round(value, 1)

        final_list = [
            {
                "zaman":       time,
                "buzdolabi":   devices["buzdolabi"],
                "esp32_ana":   devices["ana_sayac"],
                "utu":         devices["utu"],
                "seyyar_priz": devices["seyyar_priz"]
            }
            for time, devices in time_map.items()
        ]

        final_list.sort(key=lambda x: x["zaman"])
        return final_list

    except Exception as e:
        print(f"GRAFIK HATASI: {e}")
        return []
    finally:
        client.close()


# ==========================================
# 6. SAGLIK KONTROLU
# ==========================================
@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"mesaj": "Akilli Ev NILM API calisiyor."}

@app.api_route("/ping", methods=["GET", "HEAD"])
def ping():
    return {"status": "ok"}


# ==========================================
# 7. SUNUCU
# ==========================================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
