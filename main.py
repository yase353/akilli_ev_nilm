from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
import uvicorn
from datetime import datetime, timezone, timedelta

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

    # Flutter'ın beklediği anahtarlar (key) sabit kalmalı
    cihaz_sonuclari = {
        "ana_sayac": {"cihaz": "Ana Hat (ESP32)", "tuketim": "0W", "saatlik_maliyet": "0.0 TL", "durum": "Kapalı"},
        "buzdolabi": {"cihaz": "Akıllı Priz - Buzdolabı", "tuketim": "0W", "saatlik_maliyet": "0.0 TL", "durum": "Kapalı"},
        "seyyar_priz": {"cihaz": "Seyyar Priz", "tuketim": "0W", "saatlik_maliyet": "0.0 TL", "durum": "Kapalı"}
    }

    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -5m)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> last()
    '''
    
    try:
        result = query_api.query(org=INFLUX_ORG, query=query)
        now = datetime.now(timezone.utc)
        
        for table in result:
            for record in table.records:
                tag = str(record.values.get("cihaz") or record.values.get("device_id") or "").lower().strip()
                watt = record.get_value()
                last_time = record.get_time()

                if (now - last_time).total_seconds() > 120: # 2 dakika tolerans
                    continue

                # Eşleştirme Mantığı
                target_key = None
                if any(x in tag for x in ["ana", "esp"]): target_key = "ana_sayac"
                elif any(x in tag for x in ["buz", "utu"]): target_key = "buzdolabi"
                elif any(x in tag for x in ["seyyar", "camasir", "priz"]): target_key = "seyyar_priz"

                if target_key:
                    cihaz_sonuclari[target_key].update({
                        "tuketim": f"{round(watt, 1)}W",
                        "saatlik_maliyet": f"{round((watt/1000) * 3.5, 2)} TL",
                        "durum": "Aktif" if watt > 5 else "Beklemede"
                    })
        return list(cihaz_sonuclari.values())
    except:
        return list(cihaz_sonuclari.values())
    finally:
        client.close()

# ==========================================
# 3. EV DURUMU (Ana Sayfa Özet Verileri)
# ==========================================
@app.get("/ev-durumu")
def get_ev_durumu():
    client = get_influx_client()
    query_api = client.query_api()
    
    anlik_query = f'''
        from(bucket: "{INFLUX_BUCKET}") 
        |> range(start: -2m) 
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim") 
        |> filter(fn: (r) => r["cihaz"] == "ana_sayac" or r["cihaz"] == "esp32_ana")
        |> last()
    '''
    
    fatura_query = f'''
        from(bucket: "{INFLUX_BUCKET}") 
        |> range(start: -24h) 
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim") 
        |> filter(fn: (r) => r["_field"] == "guc")
        |> mean()
    '''
    
    try:
        anlik_result = query_api.query(org=INFLUX_ORG, query=anlik_query)
        anlik_watt = 0.0
        is_alive = False
        
        for table in anlik_result:
            for record in table.records:
                anlik_watt = record.get_value()
                if (datetime.now(timezone.utc) - record.get_time()).total_seconds() < 120:
                    is_alive = True

        fatura_result = query_api.query(org=INFLUX_ORG, query=fatura_query)
        ortalama_watt = 0.0
        for table in fatura_result:
            for record in table.records:
                ortalama_watt = record.get_value() or 0.0

        aylik_kwh = (ortalama_watt * 24 * 30) / 1000
        # Türkiye Kademeli Tarife (2024 simülasyonu)
        tahmini_fatura = (min(aylik_kwh, 240) * 2.07) + (max(0, aylik_kwh - 240) * 3.10)

        return {
            "durum": "Basarili" if is_alive else "Cevrimdisi",
            "tahmini_fatura": f"{round(tahmini_fatura, 2)} TL",
            "aylik_tuketim_kwh": f"{round(aylik_kwh, 1)}",
            "anlik_toplam_watt": f"{round(anlik_watt, 1)} W"
        }
    except Exception as e:
        return {"durum": "Hata", "mesaj": str(e)}
    finally:
        client.close()

# ==========================================
# 4. ENERJİ GEÇMİŞİ (GRAFİK İÇİN)
# ==========================================
@app.get("/enerji-gecmisi")
def get_enerji_gecmisi(saat: int = 1): 
    client = get_influx_client()
    query_api = client.query_api()
    
    # Süreye göre veri sıklığı ayarı (Flutter grafiği yorulmasın diye)
    if saat <= 1: pencere = "1m"
    elif saat <= 24: pencere = "5m"
    else: pencere = "1h"

    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -{saat}h)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> aggregateWindow(every: {pencere}, fn: mean, createEmpty: true)
        |> fill(value: 0.0)
    '''
    
    try:
        result = query_api.query(org=INFLUX_ORG, query=query)
        time_map = {}
        
        for table in result:
            for record in table.records:
                # ISO formatında zamanı al (Flutter DateTime.parse için uygun)
                time = record.get_time().isoformat()
                value = record.get_value() or 0.0
                tag = str(record.values.get("cihaz") or "").lower().strip()
                
                if time not in time_map:
                    time_map[time] = {"ana_sayac": 0.0, "buzdolabi": 0.0, "seyyar_priz": 0.0}
                
                # Esnek eşleştirme ile veriyi doğru kategoriye yaz
                if any(x in tag for x in ["ana", "esp"]):
                    time_map[time]["ana_sayac"] = round(value, 1)
                elif any(x in tag for x in ["buz", "utu"]):
                    time_map[time]["buzdolabi"] = round(value, 1)
                elif any(x in tag for x in ["seyyar", "camasir", "priz"]):
                    time_map[time]["seyyar_priz"] = round(value, 1)

        final_list = []
        for time, devices in time_map.items():
            final_list.append({
                "zaman": time,
                "buzdolabi": devices["buzdolabi"],
                "esp32_ana": devices["ana_sayac"],
                "seyyar_priz": devices["seyyar_priz"]
            })
            
        final_list.sort(key=lambda x: x["zaman"])
        return final_list
        
    except Exception as e:
        print(f"GRAFİK HATASI: {e}")
        return []
    finally:
        client.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
