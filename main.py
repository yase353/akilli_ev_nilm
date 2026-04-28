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

# Türkiye 2025 elektrik birim fiyatı (TL/kWh)
# İlk 240 kWh dilimi
FIYAT_DUSUK = 2.07
# 240 kWh üzeri
FIYAT_YUKSEK = 3.10

def get_influx_client():
    return InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)


# ==========================================
# 2. YARDIMCI FONKSİYONLAR
# ==========================================
def watt_to_saatlik_tl(watt: float) -> float:
    """Anlık watt değerini saatlik TL maliyete çevirir."""
    kwh_saatlik = watt / 1000.0
    # Basit hesap: ortalama birim fiyat üzerinden
    return round(kwh_saatlik * FIYAT_DUSUK, 4)

def tahmin_et(guc_verileri: list) -> str:
    """
    Kural tabanlı geçici tahmin — CNN-LSTM hazır olunca burası değişecek.
    """
    if not guc_verileri:
        return "Veri Bekleniyor..."
    son_watt = guc_verileri[-1]
    if son_watt < 15:
        return "Boşta"
    elif son_watt < 80:
        return "Televizyon"
    elif son_watt < 250:
        return "Çamaşır Makinesi (Bekleme)"
    elif son_watt < 1500:
        return "Çamaşır Makinesi (Yıkama)"
    else:
        return "Ütü"

def gercek_aylik_kwh_hesapla(client: InfluxDBClient) -> float:
    """Son 30 günün gerçek tüketimini trapez yöntemiyle hesaplar."""
    query_api = client.query_api()
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -30d)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
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
            ort_watt = (w0 + w1) / 2.0
            toplam_wh += ort_watt * sure_saat

        return round(toplam_wh / 1000.0, 2)
    except Exception as e:
        print(f"FATURA HESAP HATASI: {e}")
        return 0.0

def fatura_hesapla(aylik_kwh: float) -> float:
    ilk_dilim = min(aylik_kwh, 240) * FIYAT_DUSUK
    ikinci_dilim = max(0.0, aylik_kwh - 240) * FIYAT_YUKSEK
    return round(ilk_dilim + ikinci_dilim, 2)

def son_watt_getir(client: InfluxDBClient, cihaz_tag: str) -> float:
    """
    Belirli bir cihaz tag'ine ait son 2 dakikadaki
    ortalama watt değerini döndürür.
    cihaz_tag: InfluxDB'deki 'cihaz' tag değeriyle eşleşmeli.
    """
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
# 3. EV DURUMU ENDPOİNTİ
# ==========================================
@app.api_route("/ev-durumu", methods=["GET", "HEAD"])
def get_ev_durumu():
    client = get_influx_client()
    query_api = client.query_api()
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -1m)
        |> filter(fn: (r) => r["_measurement"] == "gercek_tuketim")
        |> filter(fn: (r) => r["_field"] == "guc")
        |> sort(columns: ["_time"])
    '''
    try:
        results = query_api.query(org=INFLUX_ORG, query=query)
        guc_noktalari = []
        anlik_watt = 0.0
        is_alive = False

        for table in results:
            for record in table.records:
                val = record.get_value() or 0.0
                guc_noktalari.append(val)
                anlik_watt = val
                gecen_sure = (datetime.now(timezone.utc) - record.get_time()).total_seconds()
                if gecen_sure < 120:
                    is_alive = True

        aktif_cihaz = tahmin_et(guc_noktalari)
        aylik_kwh = gercek_aylik_kwh_hesapla(client)
        tahmini_fatura = fatura_hesapla(aylik_kwh)

        return {
          "durum": "Basarili",
         "tahmini_fatura": "0.0 TL",
         "aylik_tuketim_kwh": "0.0",
         "anlik_toplam_watt": "0.0 W",
         "aktif_cihaz": "Test modu"
        }
    except Exception as e:
        return {"durum": "Hata", "mesaj": str(e)}
    finally:
        client.close()

# ==========================================
# 4. CİHAZ DETAYLARI ENDPOİNTİ (YENİ)
# ==========================================
@app.get("/cihaz-detaylari")
def get_cihaz_detaylari():
    """
    Her cihazın anlık watt ve saatlik TL maliyetini döndürür.

    InfluxDB'deki 'cihaz' tag değerleri buradaki listede
    tanımlı isimlerle birebir eşleşmeli.
    Eğer tag adların farklıysa aşağıdaki 'tag' alanlarını güncelle.
    """
    cihazlar = [
        {"ad": "Ana Sayaç (ESP32)", "tag": "esp32_ana",   "ikon": "electric_meter"},
        {"ad": "Buzdolabı",         "tag": "buzdolabi",   "ikon": "kitchen"},
        {"ad": "Seyyar Priz",       "tag": "seyyar_priz", "ikon": "power"},
    ]

    client = get_influx_client()
    try:
        sonuclar = []
        for cihaz in cihazlar:
            watt = son_watt_getir(client, cihaz["tag"])
            saatlik_tl = watt_to_saatlik_tl(watt)
            durum = "Aktif" if watt > 5 else "Bekleme"

            sonuclar.append({
                "cihaz": cihaz["ad"],
                "ikon": cihaz["ikon"],
                "anlik_watt": f"{watt} W",
                "saatlik_maliyet": f"{saatlik_tl} TL/saat",
                "durum": durum
            })

        return sonuclar
    except Exception as e:
        return [{"cihaz": "Hata", "mesaj": str(e)}]
    finally:
        client.close()


# ==========================================
# 5. ENERJİ GEÇMİŞİ ENDPOİNTİ
# ==========================================
@app.get("/enerji-gecmisi")
def get_enerji_gecmisi(saat: int = 1):
    client = get_influx_client()
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
        result = query_api.query(org=INFLUX_ORG, query=query)
        time_map = {}

        for table in result:
            for record in table.records:
                time = record.get_time().isoformat()
                value = record.get_value() or 0.0
                tag = str(record.values.get("cihaz") or "").lower().strip()

                if time not in time_map:
                    time_map[time] = {
                        "ana_sayac": 0.0,
                        "buzdolabi": 0.0,
                        "utu": 0.0,
                        "seyyar_priz": 0.0
                    }

                if any(x in tag for x in ["ana", "esp"]):
                    time_map[time]["ana_sayac"] = round(value, 1)
                elif any(x in tag for x in ["buz", "dolap"]):
                    time_map[time]["buzdolabi"] = round(value, 1)
                elif any(x in tag for x in ["utu", "ütü"]):
                    time_map[time]["utu"] = round(value, 1)
                elif any(x in tag for x in ["seyyar", "camasir", "çamaşır", "priz", "tv", "televizyon"]):
                    time_map[time]["seyyar_priz"] = round(value, 1)

        final_list = [
            {
                "zaman": time,
                "buzdolabi": devices["buzdolabi"],
                "esp32_ana": devices["ana_sayac"],
                "utu": devices["utu"],
                "seyyar_priz": devices["seyyar_priz"]
            }
            for time, devices in time_map.items()
        ]

        final_list.sort(key=lambda x: x["zaman"])
        return final_list

    except Exception as e:
        print(f"GRAFİK HATASI: {e}")
        return []
    finally:
        client.close()


# ==========================================
# 6. SAĞLIK KONTROLÜ
# ==========================================
@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"mesaj": "Akıllı Ev NILM API çalışıyor."}

# ==========================================
# 7. SUNUCU (yalnızca bir kez, en sonda)
# ==========================================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
