from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
import uvicorn
from datetime import datetime

app = FastAPI(title="Akıllı Ev NILM Backend")

# CORS Ayarları (Mobil uygulamanın erişebilmesi için şart)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# InfluxDB Bilgileri
INFLUX_URL = "https://eu-central-1-1.aws.cloud2.influxdata.com"
INFLUX_TOKEN = "Itz6VHbsOtjsf1sBlQTgecv33SvF84M1rbukAO05dnAgVA9FFW6KF9tXsGHtB9WCUGx-s78LACnQ8ev7GyefMQ=="
INFLUX_ORG = "2a22ab52153e142d"
INFLUX_BUCKET = "tez_verileri"

def get_influx_client():
    return InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)

# --- 1. ANA SAYFA VE FATURA ANALİZİ (24 SAATLİK VERİ) ---
@app.get("/ev-durumu")
def get_home_status():
    client = get_influx_client()
    query_api = client.query_api()
    
    # Son 24 saatlik ortalama güç tüketimi (Öğrenme/Analiz için)
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -24h)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> mean()
    '''
    
    try:
        result = query_api.query(org=INFLUX_ORG, query=query)
        ortalama_watt = 0.0
        for table in result:
            for record in table.records:
                ortalama_watt = record.get_value()

        # Aylık Fatura Tahmini: (Ort. Watt * 24saat * 30gün) / 1000 * 2.59 TL
        aylik_kwh = (ortalama_watt * 24 * 30) / 1000
        tahmini_fatura = aylik_kwh * 2.59

        return {
            "durum": "Başarılı",
            "anlik_guc_watt": round(ortalama_watt, 1),
            "cos_phi": 0.98,
            "tahmini_fatura_tl": round(tahmini_fatura, 2)
        }
    except Exception as e:
        return {"durum": f"Hata: {str(e)}", "anlik_guc_watt": 0, "cos_phi": 0, "tahmini_fatura_tl": 0}
    finally:
        client.close()

# --- 2. GRAFİK VERİSİ (SON 1 SAATLİK AKIŞ) ---
@app.get("/enerji-gecmisi")
def get_energy_history():
    client = get_influx_client()
    query_api = client.query_api()
    
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -1h)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> aggregateWindow(every: 2m, fn: mean, createEmpty: false)
    '''
    try:
        result = query_api.query(org=INFLUX_ORG, query=query)
        return [{"zaman": r.get_time().strftime("%H:%M"), "deger": round(r.get_value(), 2)} 
                for t in result for r in t.records]
    except:
        return []
    finally:
        client.close()

# --- 3. CİHAZ TABLOSU ---
@app.get("/cihaz-detaylari")
def get_device_details():
    client = get_influx_client()
    query_api = client.query_api()
    
    cihazlar = {
        "Ana Hat (ESP32)": {"cihaz": "Ana Hat", "tuketim": "0W", "maliyet": "0 TL", "durum": "Kapalı"},
        "Akıllı Priz - Buzdolabı": {"cihaz": "Buzdolabı", "tuketim": "0W", "maliyet": "0 TL", "durum": "Kapalı"}
    }
    
    query = f'from(bucket: "{INFLUX_BUCKET}") |> range(start: -10m) |> last()'
    
    try:
        result = query_api.query(org=INFLUX_ORG, query=query)
        for table in result:
            for record in table.records:
                watt = record.get_value()
                device = record.values.get("device", "Priz")
                key = "Akıllı Priz - Buzdolabı" if "buz" in device.lower() else "Ana Hat (ESP32)"
                
                cihazlar[key].update({
                    "tuketim": f"{round(watt,1)}W",
                    "maliyet": f"{round((watt/1000)*2.59, 2)} TL",
                    "durum": "Aktif" if watt > 5 else "Beklemede"
                })
        return list(cihazlar.values())
    except:
        return list(cihazlar.values())
    finally:
        client.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
