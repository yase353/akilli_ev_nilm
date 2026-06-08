# ============================================================
# sentetik_tek_nokta.py
# GitHub Actions tarafından her 5 dakikada bir çalıştırılır
# Tek bir veri noktası üretip InfluxDB'ye yazar
# ============================================================

import os
import numpy as np
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

# ============================================================
# BAĞLANTI — GitHub Secrets'tan gelir
# ============================================================
INFLUX_URL    = "https://eu-central-1-1.aws.cloud2.influxdata.com"
INFLUX_TOKEN  = os.environ["INFLUX_TOKEN"]
INFLUX_ORG    = "2a22ab52153e142d"
INFLUX_BUCKET = "tez_verileri"

# ============================================================
# CİHAZ WATT DEĞERLERİ — EV1
# ============================================================
W_TV        = 85
W_SAC       = 1650
W_SUPURGE   = 1100
W_FIRIN     = 1800
W_CAM_I     = 2100
W_CAM_D     = 420
W_UTU       = 1200
W_BUZ_AC    = 125
W_BUZ_KP    = 4

def g(mu, sigma=None):
    if sigma is None:
        sigma = mu * 0.08
    return max(0.0, np.random.normal(mu, sigma))

def aralik(saat, bas, bit, sapma=0.0):
    return (bas + sapma) <= saat < (bit + sapma)

def ev1_cihazlar(saat, gun):
    # Sabit seed — aynı dakikada tutarlı sonuç
    np.random.seed(int(saat * 60) % 1000 + gun * 1000)
    w = {}
    s = np.random.uniform(-0.1, 0.1)  # küçük sabit sapma

    # TV
    tv = 0.0
    if gun == 0:
        if aralik(saat,7.0,8.5,s) or aralik(saat,10.0,12.0,s) or aralik(saat,15.0,17.0,s) or aralik(saat,18.0,22.0,s):
            tv = g(W_TV)
    elif gun == 1:
        if aralik(saat,10.0,12.0,s) or aralik(saat,17.0,22.0,s):
            tv = g(W_TV)
    elif gun == 2:
        if aralik(saat,10.0,12.0,s) or aralik(saat,16.0,23.0,s):
            tv = g(W_TV)
    elif gun == 3:
        if aralik(saat,10.0,12.0,s) or aralik(saat,16.0,23.0,s):
            tv = g(W_TV)
    elif gun == 4:
        if aralik(saat,10.0,12.0,s) or aralik(saat,17.0,24.0,s):
            tv = g(W_TV)
    elif gun == 5:
        if aralik(saat,11.0,13.0,s) or aralik(saat,16.0,23.0,s):
            tv = g(W_TV)
    elif gun == 6:
        if aralik(saat,9.0,12.0,s) or aralik(saat,16.0,23.0,s):
            tv = g(W_TV)
    w["televizyon"] = tv

    # Saç kurutma
    sac = 0.0
    if gun == 0 and (aralik(saat,8.17,8.33,s) or aralik(saat,22.5,22.67,s)):
        sac = g(W_SAC)
    elif gun == 1 and (aralik(saat,8.33,8.45,s) or aralik(saat,22.0,22.17,s)):
        sac = g(W_SAC)
    elif gun == 2 and (aralik(saat,8.33,8.45,s) or aralik(saat,22.0,22.17,s)):
        sac = g(W_SAC)
    elif gun == 3 and (aralik(saat,8.25,8.33,s) or aralik(saat,22.17,22.33,s)):
        sac = g(W_SAC)
    elif gun == 4 and aralik(saat,8.17,8.33,s):
        sac = g(W_SAC)
    elif gun == 6 and aralik(saat,22.17,22.33,s):
        sac = g(W_SAC)
    w["sac_kurutma"] = sac

    # Süpürge
    sup = 0.0
    if gun == 0 and aralik(saat,12.33,12.67,s):
        sup = g(W_SUPURGE)
    elif gun == 2 and aralik(saat,12.5,13.0,s):
        sup = g(W_SUPURGE)
    elif gun == 5 and aralik(saat,12.5,13.0,s):
        sup = g(W_SUPURGE)
    elif gun == 6 and aralik(saat,12.5,13.0,s):
        sup = g(W_SUPURGE)
    w["supurge"] = sup

    # Fırın
    firin = 0.0
    if gun == 1 and aralik(saat,16.0,16.5,s):
        firin = g(W_FIRIN)
    elif gun == 2 and aralik(saat,16.0,16.5,s):
        firin = g(W_FIRIN)
    elif gun == 5 and aralik(saat,16.0,16.67,s):
        firin = g(W_FIRIN)
    w["firin"] = firin

    # Çamaşır makinesi
    cam = 0.0
    if gun == 2:
        if aralik(saat,16.67,17.67,s):
            cam = g(W_CAM_I) if saat < 17.17 else g(W_CAM_D)
        elif aralik(saat,17.83,18.83,s):
            cam = g(W_CAM_I) if saat < 18.33 else g(W_CAM_D)
    elif gun == 4:
        if aralik(saat,16.67,17.67,s):
            cam = g(W_CAM_I) if saat < 17.17 else g(W_CAM_D)
    elif gun == 5:
        if aralik(saat,13.67,14.67,s):
            cam = g(W_CAM_I) if saat < 14.17 else g(W_CAM_D)
        elif aralik(saat,14.83,15.83,s):
            cam = g(W_CAM_I) if saat < 15.33 else g(W_CAM_D)
    w["camasir_makinesi"] = cam

    # Ütü
    utu = 0.0
    if gun == 2 and aralik(saat,18.0,18.5,s):
        utu = g(W_UTU)
    elif gun == 3 and aralik(saat,13.0,14.5,s):
        utu = g(W_UTU)
    elif gun == 6 and aralik(saat,13.0,14.5,s):
        utu = g(W_UTU)
    w["utu"] = utu

    return w

def pf_hesapla(cihazlar):
    if cihazlar.get("camasir_makinesi", 0) > 100:
        return round(np.random.uniform(0.65, 0.78), 2)
    if (cihazlar.get("firin", 0) > 100 or
        cihazlar.get("utu", 0) > 100 or
        cihazlar.get("sac_kurutma", 0) > 100 or
        cihazlar.get("supurge", 0) > 100):
        return round(np.random.uniform(0.95, 1.0), 2)
    if cihazlar.get("televizyon", 0) > 50:
        return round(np.random.uniform(0.62, 0.72), 2)
    return round(np.random.uniform(0.80, 0.93), 2)

# ============================================================
# TEK NOKTA ÜRET VE YAZ
# ============================================================
zaman   = datetime.now(timezone.utc)
tr_saat = (zaman.hour + 3) % 24
saat    = tr_saat + zaman.minute / 60.0 + zaman.second / 3600.0
gun     = zaman.weekday()
voltaj  = round(np.random.normal(228, 2.5), 1)
ts      = int(zaman.timestamp())

# Buzdolabı döngüsü
faz = (zaman.hour * 60 + zaman.minute) % 60
buz = max(1, round(g(W_BUZ_AC) if faz < 12 else g(W_BUZ_KP, 0.5), 1))

# Cihazlar
c1         = ev1_cihazlar(saat, gun)
arka_plan  = g(30, 5)
aydinlatma = g(80, 15) if 18.0 <= saat < 23.0 else g(25, 8)
ana        = max(60, round(sum(c1.values()) + buz + arka_plan + aydinlatma, 1))
pf         = pf_hesapla(c1)

# InfluxDB bağlantısı
client    = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)

kayitlar = [
    f"gercek_tuketim,cihaz=ana_sayac,ev=ev1 guc={ana},voltaj={voltaj},akim={round(ana/voltaj,3)},guc_faktoru={pf},frekans=50.0",
    f"gercek_tuketim,cihaz=buzdolabi,ev=ev1 guc={buz},voltaj={voltaj},akim={round(buz/voltaj,3)},frekans=50.0",
]
for cihaz, watt in c1.items():
    if watt > 5:
        kayitlar.append(
            f"gercek_tuketim,cihaz={cihaz},ev=ev1 guc={round(watt,1)},voltaj={voltaj},akim={round(watt/voltaj,3)},frekans=50.0"
        )

for kayit in kayitlar:
    write_api.write(
        bucket=INFLUX_BUCKET, org=INFLUX_ORG,
        write_precision="s", record=kayit, time=ts
    )

client.close()

aktif = [k for k, v in c1.items() if v > 5]
print(f"OK | TR:{tr_saat:02d}:{zaman.minute:02d} | Ana:{ana}W Buz:{buz}W Aktif:{aktif}")
