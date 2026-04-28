from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
import uvicorn
from datetime import datetime, timezone

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
                # Cihaz ismini etiketlerden bul
                tag_name = record.values.get("cihaz") or record.values.get("device_id")
                watt = record.get_value()
                last_time = record.get_time()

                # CANLI KONTROL: Eğer son veri 60 saniyeden eskiyse işleme (Cihaz sökülmüş)
                if (now - last_time).total_seconds() > 60:
                    continue

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
    
    # Anlık durumu kontrol etmek için son 1 dakikaya bakıyoruz
    anlik_query = f'''
        from(bucket: "{INFLUX_BUCKET}") 
        |> range(start: -1m) 
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim") 
        |> filter(fn: (r) => r["cihaz"] == "ana_sayac")
        |> last()
    '''
    
    # Fatura için son 24 saatlik ortalama
    fatura_query = f'from(bucket: "{INFLUX_BUCKET}") |> range(start: -24h) |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim") |> mean()'
    
    try:
        # ANLIK GÜÇ VE CANLILIK KONTROLÜ
        anlik_result = query_api.query(org=INFLUX_ORG, query=anlik_query)
        anlik_watt = 0.0
        is_alive = False
        
        if anlik_result:
            for table in anlik_result:
                for record in table.records:
                    anlik_watt = record.get_value()
                    # Zaman kontrolü
                    if (datetime.now(timezone.utc) - record.get_time()).total_seconds() < 60:
                        is_alive = True

        # FATURA HESAPLAMA
        fatura_result = query_api.query(org=INFLUX_ORG, query=fatura_query)
        ortalama_watt = 0.0
        for table in fatura_result:
            for record in table.records:
                ortalama_watt += record.get_value()

        aylik_kwh = (ortalama_watt * 24 * 30) / 1000
        kademe_siniri = 240
        dusuk_birim_fiyat = 2.07
        yuksek_birim_fiyat = 3.10

        if aylik_kwh <= kademe_siniri:
            tahmini_fatura = aylik_kwh * dusuk_birim_fiyat
        else:
            tahmini_fatura = (kademe_siniri * dusuk_birim_fiyat) + ((aylik_kwh - kademe_siniri) * yuksek_birim_fiyat)

        return {
            "durum": "Basarili" if is_alive else "Cevrimdisi",
            "tahmini_fatura": f"{round(tahmini_fatura, 2)} TL" if is_alive else "0.0 TL",
            "aylik_tuketim_kwh": f"{round(aylik_kwh, 1)}" if is_alive else "0",
            "anlik_toplam_watt": f"{round(anlik_watt, 1)} W" if is_alive else "0 W"
        }
    except Exception as e:
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
    
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -{saat}h)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
    '''
    
    try:
        result = query_api.query(org=INFLUX_ORG, query=query)
        time_map = {}
        
        for table in result:
            for record in table.records:
                time = record.get_time().isoformat()
                value = record.get_value() or 0.0
                tag = record.values.get("cihaz") or record.values.get("device_id") or "bilinmeyen"
                
                if time not in time_map:
                    time_map[time] = {"ana_sayac": 0.0, "buzdolabi": 0.0, "seyyar_priz": 0.0}
                
                # Eşleştirme: Influx'tan ne gelirse gelsin bizim anahtarlarımıza ata
                if tag in ["ana_sayac", "esp32_ana"]:
                    time_map[time]["ana_sayac"] = round(value, 1)
                elif tag == "buzdolabi":
                    time_map[time]["buzdolabi"] = round(value, 1)
                elif tag == "seyyar_priz":
                    time_map[time]["seyyar_priz"] = round(value, 1)

        final_list = []
        for time, devices in time_map.items():
            # INFLUX -> FLUTTER EŞLEŞTİRMESİ
            # Influx'ta 'utu' olan veriyi Flutter'ın 'buzdolabi' anahtarına koyuyoruz
            buzdolabi_verisi = devices.get("utu", 0.0) 
            
            # Influx'ta 'camasir_makinesi' olan veriyi Flutter'ın 'seyyar_priz' anahtarına koyuyoruz
            seyyar_verisi = devices.get("camasir_makinesi", 0.0)
            
            # Influx'ta 'ana_sayac' veya 'esp32_ana' olanı ana hatta koyuyoruz
            ana_hat_verisi = devices.get("ana_sayac") or devices.get("esp32_ana") or 0.0

            final_list.append({
                "zaman": time,
                "buzdolabi": buzdolabi_verisi,
                "esp32_ana": ana_hat_verisi,
                "seyyar_priz": seyyar_verisi
            })
            
        final_list.sort(key=lambda x: x["zaman"])
        return final_list
        
    except Exception as e:
        print(f"HATA: {e}")
        return []
    finally:
        client.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
