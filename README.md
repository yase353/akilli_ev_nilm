# Akıllı Ev NILM Sistemi — Backend & Model

IoT tabanlı gerçek zamanlı Müdahalesiz Yük İzleme (NILM) sistemi. ESP32 ve Shelly Plug S akıllı prizlerden toplanan enerji verilerini CNN-LSTM derin öğrenme modeliyle analiz ederek aktif cihazları tespit eder.

## Proje Hakkında

Bu proje, tek bir ana hat ölçümünden hangi ev cihazının çalıştığını tespit eden bir NILM sistemidir. Güç tüketimi ve güç faktörü birlikte model girdisi olarak kullanılarak cihaz ayrıştırma doğruluğu artırılmıştır.

## Sistem Mimarisi

- **Donanım:** ESP32 + PZEM-004T (ana hat) · Shelly Plug S Gen3 (cihaz bazlı)
- **Veritabanı:** InfluxDB Cloud (AWS eu-central-1)
- **Backend:** FastAPI → Render.com
- **Model:** CNN-LSTM (Google Colab'da eğitildi)
- **Frontend:** Flutter → [akilli-ev-web](https://github.com/yase353/akilli-ev-web)

## Dosyalar

| Dosya | Açıklama |
|-------|----------|
| `main.py` | FastAPI backend — tüm endpoint'ler |
| `nilm_model.keras` | Eğitilmiş CNN-LSTM modeli |
| `scaler.pkl` | Özellik normalizasyon ölçekleyici |
| `label_encoder.pkl` | Cihaz sınıfı etiket kodlayıcı |
| `requirements.txt` | Python bağımlılıkları |

## API Endpoint'leri

| Endpoint | Açıklama |
|----------|----------|
| `GET /ev-durumu` | Anlık güç, AI cihaz tahmini, projeksiyon |
| `GET /cihaz-detaylari` | Cihaz bazlı anlık watt ve maliyet |
| `GET /enerji-gecmisi` | Pasta grafik için kWh dağılımı |
| `GET /grafik-gecmisi` | Çizgi grafik için zaman serisi |
| `GET /ping` | Sağlık kontrolü |

## Kurulum

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Gerekli ortam değişkenleri:
INFLUX_URL=https://eu-central-1-1.aws.cloud2.influxdata.com
INFLUX_TOKEN=your_token
INFLUX_ORG=your_org
INFLUX_BUCKET=tez_verileri

## Canlı Demo

API: https://akilli-ev-nilm-zgcq.onrender.com 
Web: https://yase353.github.io/akilli-ev-web/

## Teknolojiler

Python · FastAPI · TensorFlow · InfluxDB · Render.com
