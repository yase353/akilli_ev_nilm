import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:fl_chart/fl_chart.dart';

void main() {
  runApp(const AkilliEvApp());
}

class AkilliEvApp extends StatelessWidget {
  const AkilliEvApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Akıllı Ev NILM',
      theme: ThemeData(
        useMaterial3: true,
        colorSchemeSeed: Colors.blueAccent,
        brightness: Brightness.light,
      ),
      home: const EvDurumuSayfasi(),
    );
  }
}

// ==========================================
// DÜZELTME 1: URL'de çift slash sorunu giderildi.
// Sondaki '/' kaldırıldı; endpoint çağrılarında '$apiBaseUrl/ev-durumu' gibi
// kullanılınca '.../ev-durumu' olacak (doğru).
// ==========================================
const String apiBaseUrl = "https://akilli-ev-nilm-9.onrender.com";

// ==========================================
// ANA SAYFA
// ==========================================
class EvDurumuSayfasi extends StatefulWidget {
  const EvDurumuSayfasi({super.key});

  @override
  State<EvDurumuSayfasi> createState() => _EvDurumuSayfasiState();
}

class _EvDurumuSayfasiState extends State<EvDurumuSayfasi> {
  String durum = "Bağlanıyor...";
  String anlikWatt = "0 W";
  String aktifCihaz = "Tespit Ediliyor...";
  String fatura = "0.0 TL";
  // DÜZELTME 2: Yüklenme durumu başta true — ilk veri gelene kadar spinner göster
  bool yukleniyor = true;
  Timer? _timer;

  Future<void> verileriGetir() async {
    try {
      final response = await http
          .get(Uri.parse('$apiBaseUrl/ev-durumu'))
          .timeout(const Duration(seconds: 60));

      if (response.statusCode == 200) {
        final veri = jsonDecode(response.body);
        setState(() {
          durum = veri['durum'] ?? "Bilinmiyor";
          anlikWatt = veri['anlik_toplam_watt'] ?? "0 W";
          aktifCihaz = veri['aktif_cihaz'] ?? "Bilinmiyor";
          fatura = veri['tahmini_fatura'] ?? "0.0 TL";
          yukleniyor = false;
        });
      } else {
        setState(() {
          durum = "Sunucu Hatası (${response.statusCode})";
          yukleniyor = false;
        });
      }
    } on TimeoutException {
      setState(() {
        durum = "Zaman Aşımı — Render uyandırılıyor olabilir";
        yukleniyor = false;
      });
    } catch (e) {
      setState(() {
        durum = "Bağlantı Hatası";
        yukleniyor = false;
      });
    }
  }

  @override
  void initState() {
    super.initState();
    verileriGetir();
    _timer = Timer.periodic(
      const Duration(seconds: 5),
      (timer) => verileriGetir(),
    );
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  // ==========================================
  // DÜZELTME 3: CircularProgressIndicator artık sadece veri
  // yüklenirken gösteriliyor; veri gelince duruyor.
  // ==========================================
  Widget _buildAIPaneli() {
    IconData cihazIcon;
    Color iconColor;

    if (aktifCihaz.contains("Ütü") || aktifCihaz.contains("Utu")) {
      cihazIcon = Icons.iron;
      iconColor = Colors.orange;
    } else if (aktifCihaz.contains("Televizyon") || aktifCihaz.contains("TV")) {
      cihazIcon = Icons.tv;
      iconColor = Colors.blue;
    } else if (aktifCihaz.contains("Çamaşır") || aktifCihaz.contains("Camasir")) {
      cihazIcon = Icons.local_laundry_service;
      iconColor = Colors.teal;
    } else if (aktifCihaz.contains("Boşta") || aktifCihaz.contains("Bosta")) {
      cihazIcon = Icons.power_settings_new;
      iconColor = Colors.grey;
    } else {
      cihazIcon = Icons.psychology;
      iconColor = Colors.purple;
    }

    return Card(
      elevation: 5,
      shadowColor: iconColor.withOpacity(0.3),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          gradient: LinearGradient(
            colors: [iconColor.withOpacity(0.1), Colors.white],
          ),
        ),
        child: Row(
          children: [
            Icon(cihazIcon, size: 50, color: iconColor),
            const SizedBox(width: 20),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    "AI CANLI TESPİT",
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: Colors.grey,
                    ),
                  ),
                  Text(
                    aktifCihaz,
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: iconColor,
                    ),
                  ),
                ],
              ),
            ),
            // DÜZELTME 3: Sadece yüklenirken döner; veri gelince yeşil tik
            yukleniyor
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.green,
                    ),
                  )
                : const Icon(Icons.check_circle, color: Colors.green),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Akıllı Ev NILM Asistanı"),
        centerTitle: true,
        actions: [
          IconButton(
            onPressed: () {
              setState(() => yukleniyor = true);
              verileriGetir();
            },
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: yukleniyor
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                children: [
                  // Sistem Durum Şeridi
                  Container(
                    padding: const EdgeInsets.symmetric(
                        vertical: 8, horizontal: 16),
                    decoration: BoxDecoration(
                      color: durum == "Basarili"
                          ? Colors.green.shade100
                          : Colors.red.shade100,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.circle,
                          size: 10,
                          color: durum == "Basarili"
                              ? Colors.green
                              : Colors.red,
                        ),
                        const SizedBox(width: 8),
                        Text(
                          "Sistem: $durum",
                          style: TextStyle(
                            color: durum == "Basarili"
                                ? Colors.green.shade900
                                : Colors.red.shade900,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),

                  // AI Paneli
                  _buildAIPaneli(),
                  const SizedBox(height: 20),

                  // Anlık Güç Kartı → Grafik sayfasına geçiş
                  InkWell(
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (context) => const GrafikSayfasi(),
                      ),
                    ),
                    child: Card(
                      child: ListTile(
                        leading: const Icon(Icons.electric_bolt,
                            color: Colors.orange, size: 40),
                        title: const Text("Toplam Tüketim"),
                        subtitle: Text(
                          anlikWatt,
                          style: const TextStyle(
                              fontSize: 24, fontWeight: FontWeight.bold),
                        ),
                        trailing: const Icon(Icons.show_chart,
                            color: Colors.orange),
                      ),
                    ),
                  ),
                  const SizedBox(height: 10),

                  // Fatura Kartı
                  Card(
                    color: Colors.green.shade50,
                    child: ListTile(
                      leading: const Icon(Icons.account_balance_wallet,
                          color: Colors.green, size: 40),
                      title: const Text("Tahmini Aylık Fatura"),
                      subtitle: Text(
                        fatura,
                        style: const TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.bold,
                          color: Colors.green,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 10),

                  // Cihaz Detayları Butonu
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                        minimumSize: const Size(double.infinity, 50)),
                    onPressed: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (context) => const CihazTabloSayfasi(),
                      ),
                    ),
                    icon: const Icon(Icons.list_alt),
                    label: const Text("Tüm Cihaz Detaylarını Gör"),
                  ),
                ],
              ),
            ),
    );
  }
}

// ==========================================
// GRAFİK SAYFASI
// DÜZELTME 4: Artık tüm cihazlar ayrı renklerle gösteriliyor.
// X ekseninde gerçek saat:dakika bilgisi var.
// Hata durumunda boş ekran yerine açıklayıcı mesaj çıkıyor.
// ==========================================
class GrafikSayfasi extends StatefulWidget {
  const GrafikSayfasi({super.key});

  @override
  State<GrafikSayfasi> createState() => _GrafikSayfasiState();
}

class _GrafikSayfasiState extends State<GrafikSayfasi> {
  List<dynamic> veri = [];
  bool yukleniyor = true;
  String hata = "";
  int seciliSaat = 1;

  Future<void> verileriGetir(int saat) async {
    setState(() {
      yukleniyor = true;
      hata = "";
    });
    try {
      final response = await http
          .get(Uri.parse('$apiBaseUrl/enerji-gecmisi?saat=$saat'))
          .timeout(const Duration(seconds: 60));

      if (response.statusCode == 200) {
        setState(() {
          veri = jsonDecode(response.body);
          yukleniyor = false;
        });
      } else {
        setState(() {
          hata = "Sunucu hatası: ${response.statusCode}";
          yukleniyor = false;
        });
      }
    } catch (e) {
      setState(() {
        hata = "Veri alınamadı: $e";
        yukleniyor = false;
      });
    }
  }

  @override
  void initState() {
    super.initState();
    verileriGetir(seciliSaat);
  }

  List<FlSpot> _spotsOlustur(String alan) {
    List<FlSpot> spots = [];
    for (int i = 0; i < veri.length; i++) {
      final deger = (veri[i][alan] ?? 0).toDouble();
      spots.add(FlSpot(i.toDouble(), deger));
    }
    return spots;
  }

  String _zamanEtiketi(int index) {
    if (index < 0 || index >= veri.length) return "";
    final zaman = DateTime.tryParse(veri[index]['zaman'] ?? "");
    if (zaman == null) return "";
    return "${zaman.hour.toString().padLeft(2, '0')}:${zaman.minute.toString().padLeft(2, '0')}";
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Tüketim Analizi")),
      body: Column(
        children: [
          // Zaman aralığı seçici
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [1, 6, 24, 72].map((saat) {
                final secili = saat == seciliSaat;
                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: ChoiceChip(
                    label: Text(saat < 24 ? "${saat}s" : "${saat ~/ 24}g"),
                    selected: secili,
                    onSelected: (_) {
                      setState(() => seciliSaat = saat);
                      verileriGetir(saat);
                    },
                  ),
                );
              }).toList(),
            ),
          ),

          // Grafik veya durum mesajı
          Expanded(
            child: yukleniyor
                ? const Center(child: CircularProgressIndicator())
                : hata.isNotEmpty
                    ? Center(
                        child: Text(hata,
                            style: const TextStyle(color: Colors.red)))
                    : veri.isEmpty
                        ? const Center(child: Text("Bu aralıkta veri yok."))
                        : Padding(
                            padding: const EdgeInsets.all(16),
                            child: LineChart(
                              LineChartData(
                                lineBarsData: [
                                  // Ana Sayaç
                                  LineChartBarData(
                                    spots: _spotsOlustur("esp32_ana"),
                                    isCurved: true,
                                    color: Colors.blue,
                                    barWidth: 2,
                                    dotData: const FlDotData(show: false),
                                    belowBarData: BarAreaData(
                                      show: true,
                                      color: Colors.blue.withOpacity(0.08),
                                    ),
                                  ),
                                  // Buzdolabı
                                  LineChartBarData(
                                    spots: _spotsOlustur("buzdolabi"),
                                    isCurved: true,
                                    color: Colors.teal,
                                    barWidth: 2,
                                    dotData: const FlDotData(show: false),
                                  ),
                                  // Ütü
                                  LineChartBarData(
                                    spots: _spotsOlustur("utu"),
                                    isCurved: true,
                                    color: Colors.orange,
                                    barWidth: 2,
                                    dotData: const FlDotData(show: false),
                                  ),
                                  // Seyyar Priz
                                  LineChartBarData(
                                    spots: _spotsOlustur("seyyar_priz"),
                                    isCurved: true,
                                    color: Colors.purple,
                                    barWidth: 2,
                                    dotData: const FlDotData(show: false),
                                  ),
                                ],
                                titlesData: FlTitlesData(
                                  bottomTitles: AxisTitles(
                                    sideTitles: SideTitles(
                                      showTitles: true,
                                      interval: (veri.length / 4)
                                          .clamp(1, double.infinity),
                                      getTitlesWidget: (value, meta) {
                                        return Text(
                                          _zamanEtiketi(value.toInt()),
                                          style:
                                              const TextStyle(fontSize: 10),
                                        );
                                      },
                                    ),
                                  ),
                                  leftTitles: AxisTitles(
                                    sideTitles: SideTitles(
                                      showTitles: true,
                                      reservedSize: 40,
                                      getTitlesWidget: (value, meta) =>
                                          Text("${value.toInt()}W",
                                              style: const TextStyle(
                                                  fontSize: 10)),
                                    ),
                                  ),
                                  topTitles: const AxisTitles(
                                      sideTitles:
                                          SideTitles(showTitles: false)),
                                  rightTitles: const AxisTitles(
                                      sideTitles:
                                          SideTitles(showTitles: false)),
                                ),
                                gridData: const FlGridData(show: true),
                                borderData: FlBorderData(show: true),
                                minY: 0,
                                maxY: 3000,
                                clipData: const FlClipData.all()
                              ),
                            ),
                          ),
          ),

          // Lejant
          if (!yukleniyor && hata.isEmpty && veri.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: const [
                  _LejantItem(renk: Colors.blue, etiket: "Ana Sayaç"),
                  SizedBox(width: 12),
                  _LejantItem(renk: Colors.teal, etiket: "Buzdolabı"),
                  SizedBox(width: 12),
                  _LejantItem(renk: Colors.orange, etiket: "Ütü"),
                  SizedBox(width: 12),
                  _LejantItem(renk: Colors.purple, etiket: "Seyyar"),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _LejantItem extends StatelessWidget {
  final Color renk;
  final String etiket;
  const _LejantItem({required this.renk, required this.etiket});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(width: 12, height: 12, color: renk),
        const SizedBox(width: 4),
        Text(etiket, style: const TextStyle(fontSize: 11)),
      ],
    );
  }
}

// ==========================================
// CİHAZ TABLOSU SAYFASI
// DÜZELTME 5: /cihaz-detaylari endpoint'i artık mevcut.
// Hata durumunda boş ekran yerine açıklayıcı mesaj.
// ==========================================
class CihazTabloSayfasi extends StatefulWidget {
  const CihazTabloSayfasi({super.key});

  @override
  State<CihazTabloSayfasi> createState() => _CihazTabloSayfasiState();
}

class _CihazTabloSayfasiState extends State<CihazTabloSayfasi> {
  List<dynamic> cihazlar = [];
  bool yukleniyor = true;
  String hata = "";

  @override
  void initState() {
    super.initState();
    _verileriGetir();
  }

  Future<void> _verileriGetir() async {
    setState(() {
      yukleniyor = true;
      hata = "";
    });
    try {
      final response = await http
          .get(Uri.parse('$apiBaseUrl/cihaz-detaylari'))
          .timeout(const Duration(seconds: 60));

      if (response.statusCode == 200) {
        setState(() {
          cihazlar = jsonDecode(response.body);
          yukleniyor = false;
        });
      } else {
        setState(() {
          hata = "Sunucu hatası: ${response.statusCode}";
          yukleniyor = false;
        });
      }
    } catch (e) {
      setState(() {
        hata = "Veri alınamadı: $e";
        yukleniyor = false;
      });
    }
  }

  IconData _ikonSec(String ikonAdi) {
    switch (ikonAdi) {
      case "kitchen":
        return Icons.kitchen;
      case "electric_meter":
        return Icons.electric_meter;
      case "power":
        return Icons.power;
      default:
        return Icons.devices;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Cihaz Detayları"),
        actions: [
          IconButton(
            onPressed: _verileriGetir,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: yukleniyor
          ? const Center(child: CircularProgressIndicator())
          : hata.isNotEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.error_outline,
                          color: Colors.red, size: 48),
                      const SizedBox(height: 12),
                      Text(hata,
                          textAlign: TextAlign.center,
                          style: const TextStyle(color: Colors.red)),
                      const SizedBox(height: 12),
                      ElevatedButton(
                        onPressed: _verileriGetir,
                        child: const Text("Tekrar Dene"),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: cihazlar.length,
                  itemBuilder: (context, i) {
                    final item = cihazlar[i];
                    final aktif = item['durum'] == "Aktif";
                    return Card(
                      margin: const EdgeInsets.symmetric(vertical: 6),
                      child: ListTile(
                        leading: Icon(
                          _ikonSec(item['ikon'] ?? ""),
                          color: aktif ? Colors.green : Colors.grey,
                          size: 36,
                        ),
                        title: Text(
                          item['cihaz'] ?? "",
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text("⚡ ${item['anlik_watt'] ?? '0 W'}"),
                            Text("💰 ${item['saatlik_maliyet'] ?? '0 TL/saat'}"),
                          ],
                        ),
                        trailing: Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: aktif
                                ? Colors.green.shade100
                                : Colors.grey.shade200,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            item['durum'] ?? "",
                            style: TextStyle(
                              color: aktif ? Colors.green.shade800 : Colors.grey,
                              fontWeight: FontWeight.bold,
                              fontSize: 12,
                            ),
                          ),
                        ),
                        isThreeLine: true,
                      ),
                    );
                  },
                ),
    );
  }
}
