from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
import uvicorn
from datetime import datetime

# ==========================================
# 1. API BAŞLATMA VE CORS AYARLARI
# ==========================================
app = FastAPI(title="Akıllı Ev NILM Gelişmiş Arka Uç")

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
# ==========================================
# 2. INFLUXDB BAĞLANTI AYARLARI
# ==========================================
INFLUX_URL = "https://eu-central-1-1.aws.cloud2.influxdata.com"
INFLUX_TOKEN = "Itz6VHbsOtjsf1sBlQTgecv33SvF84M1rbukAO05dnAgVA9FFW6KF9tXsGHtB9WCUGx-s78LACnQ8ev7GyefMQ=="
INFLUX_ORG = "2a22ab52153e142d"
INFLUX_BUCKET = "tez_verileri"

def get_influx_client():
    return InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)

# ==========================================
# 3. ENDPOINT'LER (VERİ KAPILARI)
# ==========================================

@app.get("/ev-durumu")
def get_home_status():
    """Ana sayfa kartları için anlık veriler"""
    client = get_influx_client()
    query_api = client.query_api()

    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -5m)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc" or r["_field"] == "cos_phi")
        |> last()
    '''
    
    try:
        result = query_api.query(org=INFLUX_ORG, query=query)
        guc_degeri = 0.0
        cos_phi_degeri = 1.0 

        for table in result:
            for record in table.records:
                if record.get_field() == "guc":
                    guc_degeri = record.get_value()
                elif record.get_field() == "cos_phi":
                    cos_phi_degeri = record.get_value()

        elektrik_birim_fiyat = 2.59 
        tahmini_fatura = (guc_degeri / 1000) * 24 * 30 * elektrik_birim_fiyat

        return {
            "durum": "Başarılı",
            "anlik_guc_watt": round(guc_degeri, 2),
            "cos_phi": round(cos_phi_degeri, 2),
            "tahmini_fatura_tl": round(tahmini_fatura, 2)
        }
    except Exception as e:
        return {"durum": "Hata", "mesaj": str(e)}
    finally:
        client.close()

@app.get("/enerji-gecmisi")
def get_energy_history():
    """Grafik için son 1 saatlik güç verisi (5 dakikalık ortalamalarla)"""
    client = get_influx_client()
    query_api = client.query_api()

    # Grafik için zaman serisi sorgusu
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -1h)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> aggregateWindow(every: 5m, fn: mean, createEmpty: false)
    '''
    
    try:
        result = query_api.query(org=INFLUX_ORG, query=query)
        gecmis_liste = []

        for table in result:
            for record in table.records:
                gecmis_liste.append({
                    "zaman": record.get_time().strftime("%H:%M"),
                    "deger": round(record.get_value(), 2)
                })
        
        return gecmis_liste
    except Exception as e:
        return []
    finally:
        client.close()

@app.get("/cihaz-detaylari")
def get_device_details():
    """Tablo için çalışan cihazların detaylı listesi"""
    # Burası ileride yapay zeka modelinden gelecek. 
    # Şimdilik UI testleri için dinamik-simüle veri döndürüyoruz.
    return [
        {"cihaz": "Buzdolabı", "tuketim": "150W", "saatlik_maliyet": "0.38 TL", "durum": "Aktif"},
        {"cihaz": "Çamaşır Makinesi", "tuketim": "2100W", "saatlik_maliyet": "5.44 TL", "durum": "Aktif"},
        {"cihaz": "Klima", "tuketim": "0W", "saatlik_maliyet": "0.00 TL", "durum": "Kapalı"},
        {"cihaz": "Aydınlatma", "tuketim": "40W", "saatlik_maliyet": "0.10 TL", "durum": "Aktif"},
    ]

# ==========================================
# 4. ÇALIŞTIRMA
# ==========================================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)