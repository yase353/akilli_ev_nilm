from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
import uvicorn
from datetime import datetime

# ==========================================
# 1. API BAŞLATMA VE AYARLAR
# ==========================================
app = FastAPI(title="Akıllı Ev NILM - Gelişmiş Arka Uç")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_ngrok_bypass_header(request, call_next):
    response = await call_next(request)
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response

INFLUX_URL = "https://eu-central-1-1.aws.cloud2.influxdata.com"
INFLUX_TOKEN = "Itz6VHbsOtjsf1sBlQTgecv33SvF84M1rbukAO05dnAgVA9FFW6KF9tXsGHtB9WCUGx-s78LACnQ8ev7GyefMQ=="
INFLUX_ORG = "2a22ab52153e142d"
INFLUX_BUCKET = "tez_verileri"

def get_influx_client():
    return InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)

# ==========================================
# 2. CİHAZ LİSTESİ (Tablo İçin)
# ==========================================
@app.get("/cihaz-detaylari")
def get_device_details():
    client = get_influx_client()
    query_api = client.query_api()

    # Varsayılan tablo yapısı (Anahtarlar Influx'taki cihaz isimlerinle aynı olmalı)
    cihaz_sonuclari = {
        "ana_sayac": {"cihaz": "Ana Hat (ESP32)", "tuketim": "0W", "saatlik_maliyet": "0.0 TL", "durum": "Kapalı"},
        "utu": {"cihaz": "Akıllı Priz - Buzdolabı", "tuketim": "0W", "saatlik_maliyet": "0.0 TL", "durum": "Kapalı"},
        "camasir_makinesi": {"cihaz": "Seyyar Priz", "tuketim": "0W", "saatlik_maliyet": "0.0 TL", "durum": "Kapalı"}
    }

    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -10m)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> last()
    '''
    
    try:
        result = query_api.query(org=INFLUX_ORG, query=query)
        for table in result:
            for record in table.records:
                tag_name = record.values.get("cihaz", "")
                watt = record.get_value()
                
                if tag_name in cihaz_sonuclari:
                    cihaz_sonuclari[tag_name].update({
                        "tuketim": f"{round(watt, 1)}W",
                        "saatlik_maliyet": f"{round((watt/1000) * 2.59, 2)} TL",
                        "durum": "Aktif" if watt > 5 else "Beklemede"
                    })
        return list(cihaz_sonuclari.values())
    except:
        return list(cihaz_sonuclari.values())
    finally:
        client.close()

# ==========================================
# 3. EV DURUMU (DOĞRU ENDPOINT)
# ==========================================
@app.get("/ev-durumu")  # İsim burasıydı, düzelttim.
def get_ev_durumu():
    client = get_influx_client()
    query_api = client.query_api()
    
    # Fatura tahmini için son 24 saatin ortalaması
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -24h)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> mean()
    '''
    
    try:
        result = query_api.query(org=INFLUX_ORG, query=query)
        toplam_watt = 0.0
        
        for table in result:
            for record in table.records:
                toplam_watt += record.get_value()

        aylik_kwh = (toplam_watt * 24 * 30) / 1000
        tahmini_fatura = aylik_kwh * 2.59

        # Flutter'ın beklediği "durum": "Başarılı" alanını da ekledim.
        return {
            "durum": "Başarılı",
            "tahmini_fatura": f"{round(tahmini_fatura, 2)} TL",
            "aylik_tuketim_kwh": f"{round(aylik_kwh, 1)} kWh",
            "anlik_toplam_watt": f"{round(toplam_watt, 1)} W"
        }
    except:
        return {"durum": "Hata", "tahmini_fatura": "0.0 TL", "aylik_tuketim_kwh": "0", "anlik_toplam_watt": "0"}
    finally:
        client.close()

# ==========================================
# 4. ENERJİ GEÇMİŞİ
# ==========================================
@app.get("/enerji-gecmisi")
def get_energy_history():
    client = get_influx_client()
    query_api = client.query_api()
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -1h)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
    '''
    try:
        result = query_api.query(org=INFLUX_ORG, query=query)
        return [{"zaman": r.get_time().strftime("%H:%M"), "deger": round(r.get_value(), 2)} 
                for t in result for r in t.records]
    except:
        return []
    finally:
        client.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
