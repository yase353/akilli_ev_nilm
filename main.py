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

# Ngrok/Render tarayıcı uyarısını atlatmak için
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

    # Sabit Şablon: Veri olmasa bile 3 cihaz gözüksün
    cihaz_sonuclari = {
        "Ana Hat (ESP32)": {"cihaz": "Ana Hat (ESP32)", "tuketim": "0W", "saatlik_maliyet": "0.0 TL", "durum": "Kapalı"},
        "Akıllı Priz - Buzdolabı": {"cihaz": "Akıllı Priz - Buzdolabı", "tuketim": "0W", "saatlik_maliyet": "0.0 TL", "durum": "Kapalı"},
        "Akıllı Priz - Seyyar": {"cihaz": "Akıllı Priz - Seyyar", "tuketim": "0W", "saatlik_maliyet": "0.0 TL", "durum": "Kapalı"}
    }

    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -1h)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> last()
    '''
    
    try:
        result = query_api.query(org=INFLUX_ORG, query=query)
        for table in result:
            for record in table.records:
                name = record.values.get("device", "Bilinmeyen").lower()
                watt = record.get_value()
                
                # Eşleştirme Mantığı
                key = "Akıllı Priz - Seyyar"
                if "ana" in name or "esp" in name: key = "Ana Hat (ESP32)"
                elif "buz" in name: key = "Akıllı Priz - Buzdolabı"

                cihaz_sonuclari[key].update({
                    "tuketim": f"{round(watt, 1)}W",
                    "saatlik_maliyet": f"{round((watt/1000) * 2.59, 2)} TL",
                    "durum": "Aktif" if watt > 2 else "Beklemede"
                })
        return list(cihaz_sonuclari.values())
    except:
        return list(cihaz_sonuclari.values())
    finally:
        client.close()

# ==========================================
# 3. FATURA TAHMİNİ VE ANALİZ (Yeni!)
# ==========================================
@app.get("/ev-durumu")
def get_ev_durumu():
    client = get_influx_client()
    query_api = client.query_api()

    # Son 24 saatlik ortalama güç tüketimi
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

        # Aylık Hesap: (Ortalama Watt * 24 Saat * 30 Gün) / 1000 * 2.59 TL
        aylik_kwh = (toplam_watt * 24 * 30) / 1000
        tahmini_fatura = aylik_kwh * 2.59

        return {
            "tahmini_fatura": f"{round(tahmini_fatura, 2)} TL",
            "aylik_tuketim_kwh": f"{round(aylik_kwh, 1)} kWh",
            "anlik_toplam_watt": f"{round(toplam_watt, 1)} W"
        }
    except:
        return {"tahmini_fatura": "Hesaplanıyor...", "aylik_tuketim_kwh": "0", "anlik_toplam_watt": "0"}
    finally:
        client.close()

# ==========================================
# 4. ENERJİ GEÇMİŞİ (Grafik İçin - Eski Kodu Koruduk)
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
        |> aggregateWindow(every: 5m, fn: mean, createEmpty: false)
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
