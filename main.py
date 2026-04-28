import tensorflow as tf
import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
import uvicorn
from datetime import datetime, timezone, timedelta

# ==========================================
# 1. MODEL YÜKLEME VE AYARLAR
# ==========================================
app = FastAPI(title="Akıllı Ev NILM - AI Entegre")

# Colab'da eğittiğin modeli 'enerji_modeli.h5' adıyla main.py yanına koymalısın
try:
    model = tf.keras.models.load_model('enerji_modeli.h5')
    print("AI Modeli Başarıyla Yüklendi ✅")
except Exception as e:
    model = None
    print(f"HATA: Model yüklenemedi! Sadece izleme modu aktif. {e}")

# Colab'daki eğitim sırasıyla aynı olmalı
AI_LABELS = ["Boşta", "Ütü", "Televizyon"]

# CORS ve Diğer Ayarlar (Senin mevcut ayarların)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

INFLUX_URL = "https://eu-central-1-1.aws.cloud2.influxdata.com"
INFLUX_TOKEN = "Itz6VHbsOtjsf1sBlQTgecv33SvF84M1rbukAO05dnAgVA9FFW6KF9tXsGHtB9WCUGx-s78LACnQ8ev7GyefMQ=="
INFLUX_ORG = "2a22ab52153e142d"
INFLUX_BUCKET = "tez_verileri"

def get_influx_client():
    return InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)

# ==========================================
# 2. AI TAHMİN FONKSİYONU (YENİ)
# ==========================================
def tahmin_et(guc_verileri):
    if model is None or len(guc_verileri) < 30:
        return "Öğreniliyor..."
    
    try:
        # Veriyi modelin giriş şekline (1, 30, 1) getiriyoruz
        girdi = np.array(guc_verileri[:30]).reshape(1, 30, 1)
        tahmin_dizisi = model.predict(girdi)
        en_yuksek_index = np.argmax(tahmin_dizisi)
        return AI_LABELS[en_yuksek_index]
    except:
        return "Hata"

# ==========================================
# 3. EV DURUMU (AI ENTEGRE EDİLMİŞ HALİ)
# ==========================================
@app.get("/ev-durumu")
def get_ev_durumu():
    client = get_influx_client()
    query_api = client.query_api()
    
    # AI Tahmini için son 1 dakikalık tüm verileri çekiyoruz
    ai_query = f'''
        from(bucket: "{INFLUX_BUCKET}") 
        |> range(start: -1m) 
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim") 
        |> filter(fn: (r) => r["_field"] == "guc")
        |> filter(fn: (r) => r["cihaz"] == "ana_sayac" or r["cihaz"] == "esp32_ana" or r["cihaz"] == "utu")
    '''
    
    try:
        results = query_api.query(org=INFLUX_ORG, query=ai_query)
        guc_noktalari = []
        is_alive = False
        anlik_watt = 0.0

        for table in results:
            for record in table.records:
                val = record.get_value()
                guc_noktalari.append(val)
                anlik_watt = val # En son kayıt
                # 2 dakika içinde veri gelmişse cihaz canlıdır
                if (datetime.now(timezone.utc) - record.get_time()).total_seconds() < 120:
                    is_alive = True

        # AI Tahmini Yap
        aktif_cihaz = tahmin_et(guc_noktalari)

        # Fatura Hesabı (Senin mevcut mantığın)
        aylik_kwh = (anlik_watt * 24 * 30) / 1000 # Basitleştirilmiş ortalama
        tahmini_fatura = (min(aylik_kwh, 240) * 2.07) + (max(0, aylik_kwh - 240) * 3.10)

        return {
            "durum": "Basarili" if is_alive else "Cevrimdisi",
            "tahmini_fatura": f"{round(tahmini_fatura, 2)} TL",
            "aylik_tuketim_kwh": f"{round(aylik_kwh, 1)}",
            "anlik_toplam_watt": f"{round(anlik_watt, 1)} W",
            "aktif_cihaz": aktif_cihaz # FLUTTER ARTIK BURAYI OKUYACAK
        }
    except Exception as e:
        return {"durum": "Hata", "mesaj": str(e)}
    finally:
        client.close()

# Diğer endpoint'lerin (cihaz-detaylari vb.) aynı kalabilir.
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
