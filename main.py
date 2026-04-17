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

    # Varsayılan tablo yapısı
    cihaz_sonuclari = {
        "esp32_ana": {"cihaz": "Ana Hat (ESP32)", "tuketim": "0W", "saatlik_maliyet": "0.0 TL", "durum": "Kapalı"},
        "buzdolabi": {"cihaz": "Akıllı Priz - Buzdolabı", "tuketim": "0W", "saatlik_maliyet": "0.0 TL", "durum": "Kapalı"},
        "seyyar_priz": {"cihaz": "Seyyar Priz", "tuketim": "0W", "saatlik_maliyet": "0.0 TL", "durum": "Kapalı"}
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
                tag_name = record.values.get("device_id", "") # device_id etiketine göre kontrol
                watt = record.get_value()
                
                if tag_name in cihaz_sonuclari:
                    cihaz_sonuclari[tag_name].update({
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
    
    check_query = f'from(bucket: "{INFLUX_BUCKET}") |> range(start: -2m) |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim") |> last()'
    fatura_query = f'from(bucket: "{INFLUX_BUCKET}") |> range(start: -24h) |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim") |> mean()'
    
    try:
        check_result = query_api.query(org=INFLUX_ORG, query=check_query)
        
        if not check_result or len(check_result) == 0:
            return {
                "durum": "Cevrimdisi",
                "tahmini_fatura": "0.0 TL",
                "aylik_tuketim_kwh": "0",
                "anlik_toplam_watt": "0 W"
            }

        fatura_result = query_api.query(org=INFLUX_ORG, query=fatura_query)
        toplam_watt = 0.0
        for table in fatura_result:
            for record in table.records:
                toplam_watt += record.get_value()

        aylik_kwh = (toplam_watt * 24 * 30) / 1000
        tahmini_fatura = aylik_kwh * 3.5

        return {
            "durum": "Basarili",
            "tahmini_fatura": f"{round(tahmini_fatura, 2)} TL",
            "aylik_tuketim_kwh": f"{round(aylik_kwh, 1)}",
            "anlik_toplam_watt": f"{round(toplam_watt, 1)} W"
        }
    except Exception as e:
        print(f"Hata: {e}")
        return {"durum": "Hata", "tahmini_fatura": "0.0 TL", "aylik_tuketim_kwh": "0", "anlik_toplam_watt": "0 W"}
    finally:
        client.close()

# ==========================================
# 4. ENERJİ GEÇMİŞİ (GRAFİK İÇİN)
# ==========================================
@app.get("/enerji-gecmisi")
def get_enerji_gecmisi(saat: int = 1): 
    client = get_influx_client()
    query_api = client.query_api()
    
    # Kullanıcının seçtiği saate göre dinamik sorgu
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -{saat}h)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> aggregateWindow(every: 1m, fn: mean, createEmpty: true)
        |> group(columns: ["device_id"])
    '''
    
    try:
        result = query_api.query(org=INFLUX_ORG, query=query)
        time_map = {}
        
        for table in result:
            device_id = "bilinmeyen"
            if table.records:
                # Cihaz bazlı ayrıştırma için device_id etiketini okuyoruz
                device_id = table.records[0].values.get("device_id", "bilinmeyen")
            
            for record in table.records:
                time = record.get_time().isoformat()
                value = record.get_value() or 0.0
                
                if time not in time_map:
                    time_map[time] = {}
                
                time_map[time][device_id] = round(value, 1)

        final_list = []
        for time, devices in time_map.items():
            final_list.append({
                "zaman": time,
                "buzdolabi": devices.get("buzdolabi", 0.0),
                "esp32_ana": devices.get("esp32_ana", 0.0),
                "seyyar_priz": devices.get("seyyar_priz", 0.0)
            })
            
        final_list.sort(key=lambda x: x["zaman"])
        return final_list
        
    except Exception as e:
        print(f"Grafik Hatası: {e}")
        return []
    finally:
        client.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
