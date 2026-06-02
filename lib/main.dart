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
  String durum        = "Bağlanıyor...";
  String anlikWatt    = "0 W";
  String aktifCihaz   = "Tespit Ediliyor...";
  String gunlukOrt    = "0 kWh/gün";
  String projeksiyonKwh = "0 kWh";
  String tahminiTL    = "0.0 TL";
  bool yukleniyor     = true;
  Timer? _timer;

  // Pasta grafik verisi
  List<dynamic> pastaVeri = [];

  final Map<String, Color> _renkMap = {
    'Buzdolabi':  Colors.teal,
    'Televizyon': Colors.blue,
    'Diger':      Colors.purple,
  };

  // ----------------------------------------
  // Ev durumu verisi
  // ----------------------------------------
  Future<void> verileriGetir() async {
    try {
      final response = await http
          .get(Uri.parse('$apiBaseUrl/ev-durumu'))
          .timeout(const Duration(seconds: 60));

      if (response.statusCode == 200) {
        final veri = jsonDecode(response.body);
        setState(() {
          durum           = veri['durum']             ?? "Bilinmiyor";
          anlikWatt       = veri['anlik_toplam_watt'] ?? "0 W";
          aktifCihaz      = veri['aktif_cihaz']       ?? "Bilinmiyor";
          gunlukOrt       = veri['gunluk_ort_kwh']    ?? "0 kWh/gün";
          projeksiyonKwh  = veri['projeksiyon_kwh']   ?? "0 kWh";
          tahminiTL       = veri['tahmini_fatura']    ?? "0.0 TL";
          yukleniyor      = false;
        });
      } else {
        setState(() {
          durum      = "Sunucu Hatası (${response.statusCode})";
          yukleniyor = false;
        });
      }
    } on TimeoutException {
      setState(() {
        durum      = "Zaman Aşımı — Render uyandırılıyor olabilir";
        yukleniyor = false;
      });
    } catch (e) {
      setState(() {
        durum      = "Bağlantı Hatası";
        yukleniyor = false;
      });
    }
  }

  // ----------------------------------------
  // Pasta grafik verisi
  // ----------------------------------------
  Future<void> pastaVerisiGetir() async {
    try {
      final response = await http
          .get(Uri.parse('$apiBaseUrl/enerji-gecmisi'))
          .timeout(const Duration(seconds: 60));
      if (response.statusCode == 200) {
        final json = jsonDecode(response.body);
        setState(() {
          pastaVeri = json['pasta'] ?? [];
        });
      }
    } catch (_) {}
  }

  @override
  void initState() {
    super.initState();
    verileriGetir();
    pastaVerisiGetir();
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

  // ----------------------------------------
  // AI paneli
  // ----------------------------------------
  Widget _buildAIPaneli() {
    IconData cihazIcon;
    Color    iconColor;

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
            yukleniyor
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.green),
                  )
                : const Icon(Icons.check_circle, color: Colors.green),
          ],
        ),
      ),
    );
  }

  // ----------------------------------------
  // Projeksiyon kartı — fatura kartının yerine
  // ----------------------------------------
  Widget _buildProjeksiyonKarti() {
    return Card(
      color: Colors.orange.shade50,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            const Icon(Icons.trending_up, color: Colors.orange, size: 40),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    "Bu Gidişle Aylık Tahmini",
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      color: Colors.grey,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    tahminiTL,
                    style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: Colors.orange,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    "Günlük ort: $gunlukOrt  ·  30 gün: $projeksiyonKwh",
                    style: TextStyle(
                      fontSize: 11,
                      color: Colors.grey.shade600,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ----------------------------------------
  // Pasta grafik — kWh bazlı, gerçek veriler
  // ----------------------------------------
  Widget _buildPastaGrafik() {
    final gecerliVeri = pastaVeri
        .where((d) => (d['kwh'] ?? 0).toDouble() > 0)
        .toList();

    if (gecerliVeri.isEmpty) {
      return Card(
        elevation: 3,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                "15 Günlük Cihaz Tüketim Dağılımı",
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),
              Center(
                child: Text(
                  "Henüz yeterli veri yok.\nBirkaç saat sonra tekrar bakın.",
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
                ),
              ),
              const SizedBox(height: 8),
            ],
          ),
        ),
      );
    }

    final toplam = gecerliVeri.fold<double>(
        0.0, (sum, d) => sum + (d['kwh'] ?? 0).toDouble());

    return Card(
      elevation: 3,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              "15 Günlük Cihaz Tüketim Dağılımı",
              style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 2),
            Text(
              "Gerçek ölçüm verisi · Toplam ${toplam.toStringAsFixed(1)} kWh",
              style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
            ),
            const SizedBox(height: 12),
            SizedBox(
              height: 200,
              child: Row(
                children: [
                  Expanded(
                    flex: 3,
                    child: PieChart(
                      PieChartData(
                        sections: List.generate(gecerliVeri.length, (i) {
                          final cihaz = gecerliVeri[i]['cihaz'] as String? ?? '';
                          final kwh   = (gecerliVeri[i]['kwh'] ?? 0).toDouble();
                          final yuzde = (gecerliVeri[i]['yuzde'] ?? 0).toDouble();
                          final renk  = _renkMap[cihaz] ??
                              Colors.primaries[i % Colors.primaries.length];
                          return PieChartSectionData(
                            value: kwh,
                            color: renk,
                            title: '%${yuzde.toStringAsFixed(1)}',
                            titleStyle: const TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                            radius: 80,
                          );
                        }),
                        sectionsSpace: 2,
                        centerSpaceRadius: 0,
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    flex: 2,
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: List.generate(gecerliVeri.length, (i) {
                        final cihaz = gecerliVeri[i]['cihaz'] as String? ?? '';
                        final kwh   = (gecerliVeri[i]['kwh'] ?? 0).toDouble();
                        final yuzde = (gecerliVeri[i]['yuzde'] ?? 0).toDouble();
                        final renk  = _renkMap[cihaz] ??
                            Colors.primaries[i % Colors.primaries.length];
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 5),
                          child: Row(
                            children: [
                              Container(
                                width: 12,
                                height: 12,
                                decoration: BoxDecoration(
                                  color: renk,
                                  shape: BoxShape.circle,
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      cihaz,
                                      style: const TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                    Text(
                                      '%${yuzde.toStringAsFixed(1)} · ${kwh.toStringAsFixed(1)} kWh',
                                      style: TextStyle(
                                        fontSize: 10,
                                        color: Colors.grey.shade600,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        );
                      }),
                    ),
                  ),
                ],
              ),
            ),
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
              pastaVerisiGetir();
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
                  // Sistem durumu
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

                  // AI paneli
                  _buildAIPaneli(),
                  const SizedBox(height: 20),

                  // Tüketim kartı
                  InkWell(
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                          builder: (context) => const GrafikSayfasi()),
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

                  // Projeksiyon kartı — eski fatura kartının yerine
                  _buildProjeksiyonKarti(),
                  const SizedBox(height: 10),

                  // Cihaz detayları butonu
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                        minimumSize: const Size(double.infinity, 50)),
                    onPressed: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                          builder: (context) => const CihazTabloSayfasi()),
                    ),
                    icon: const Icon(Icons.list_alt),
                    label: const Text("Tüm Cihaz Detaylarını Gör"),
                  ),
                  const SizedBox(height: 20),

                  // Pasta grafik
                  _buildPastaGrafik(),
                  const SizedBox(height: 16),
                ],
              ),
            ),
    );
  }
}

// ==========================================
// GRAFİK SAYFASI — çizgi grafik
// ==========================================
class GrafikSayfasi extends StatefulWidget {
  const GrafikSayfasi({super.key});

  @override
  State<GrafikSayfasi> createState() => _GrafikSayfasiState();
}

class _GrafikSayfasiState extends State<GrafikSayfasi> {
  List<dynamic> veri = [];
  bool yukleniyor    = true;
  String hata        = "";
  int seciliSaat     = 1;

  Future<void> verileriGetir(int saat) async {
    setState(() {
      yukleniyor = true;
      hata       = "";
    });
    try {
      final response = await http
          .get(Uri.parse('$apiBaseUrl/grafik-gecmisi?saat=$saat'))
          .timeout(const Duration(seconds: 60));
      if (response.statusCode == 200) {
        setState(() {
          veri       = jsonDecode(response.body);
          yukleniyor = false;
        });
      } else {
        setState(() {
          hata       = "Sunucu hatası: ${response.statusCode}";
          yukleniyor = false;
        });
      }
    } catch (e) {
      setState(() {
        hata       = "Veri alınamadı: $e";
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
    return List.generate(veri.length, (i) {
      final deger = (veri[i][alan] ?? 0).toDouble();
      return FlSpot(i.toDouble(), deger);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Tüketim Analizi")),
      body: Column(
        children: [
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
                            padding: const EdgeInsets.fromLTRB(4, 16, 16, 8),
                            child: LineChart(
                              LineChartData(
                                lineTouchData: LineTouchData(
                                  touchTooltipData: LineTouchTooltipData(
                                    getTooltipItems: (spots) {
                                      const etiketler = [
                                        "Ana Sayaç",
                                        "Buzdolabı",
                                        "Seyyar"
                                      ];
                                      const renkler = [
                                        Colors.blue,
                                        Colors.teal,
                                        Colors.purple
                                      ];
                                      return spots.map((spot) {
                                        final idx  = spot.barIndex;
                                        final zIdx = spot.x.toInt();
                                        String zamanStr = "";
                                        if (zIdx >= 0 && zIdx < veri.length) {
                                          final z = DateTime.tryParse(
                                              veri[zIdx]['zaman'] ?? "");
                                          if (z != null) {
                                            zamanStr =
                                                "\n${z.hour.toString().padLeft(2, '0')}:${z.minute.toString().padLeft(2, '0')}";
                                          }
                                        }
                                        return LineTooltipItem(
                                          "${idx < etiketler.length ? etiketler[idx] : ''}\n${spot.y.toStringAsFixed(1)} W$zamanStr",
                                          TextStyle(
                                            color: idx < renkler.length
                                                ? renkler[idx]
                                                : Colors.white,
                                            fontSize: 11,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        );
                                      }).toList();
                                    },
                                  ),
                                ),
                                lineBarsData: [
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
                                  LineChartBarData(
                                    spots: _spotsOlustur("buzdolabi"),
                                    isCurved: true,
                                    color: Colors.teal,
                                    barWidth: 2,
                                    dotData: const FlDotData(show: false),
                                  ),
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
                                      reservedSize: 36,
                                      interval: (veri.length / 6)
                                          .clamp(1, double.infinity),
                                      getTitlesWidget: (value, meta) {
                                        final index = value.toInt();
                                        if (index < 0 || index >= veri.length)
                                          return const SizedBox();
                                        final zaman = DateTime.tryParse(
                                            veri[index]['zaman'] ?? "");
                                        if (zaman == null)
                                          return const SizedBox();
                                        return Padding(
                                          padding:
                                              const EdgeInsets.only(top: 6),
                                          child: Text(
                                            "${zaman.hour.toString().padLeft(2, '0')}:${zaman.minute.toString().padLeft(2, '0')}",
                                            style: const TextStyle(
                                              fontSize: 11,
                                              fontWeight: FontWeight.w600,
                                              color: Colors.black87,
                                            ),
                                          ),
                                        );
                                      },
                                    ),
                                  ),
                                  leftTitles: AxisTitles(
                                    sideTitles: SideTitles(
                                      showTitles: true,
                                      reservedSize: 44,
                                      getTitlesWidget: (value, meta) => Text(
                                        "${value.toInt()}W",
                                        style:
                                            const TextStyle(fontSize: 10),
                                      ),
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
                                maxY: 1500,
                                clipData: const FlClipData.all(),
                              ),
                            ),
                          ),
          ),
          if (!yukleniyor && hata.isEmpty && veri.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: const [
                  _LejantItem(renk: Colors.blue,   etiket: "Ana Sayaç"),
                  SizedBox(width: 12),
                  _LejantItem(renk: Colors.teal,   etiket: "Buzdolabı"),
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
  final Color  renk;
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
// ==========================================
class CihazTabloSayfasi extends StatefulWidget {
  const CihazTabloSayfasi({super.key});

  @override
  State<CihazTabloSayfasi> createState() => _CihazTabloSayfasiState();
}

class _CihazTabloSayfasiState extends State<CihazTabloSayfasi> {
  List<dynamic> cihazlar = [];
  bool yukleniyor         = true;
  String hata             = "";
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _verileriGetir();
    _timer = Timer.periodic(
      const Duration(seconds: 5),
      (timer) => _verileriGetir(),
    );
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _verileriGetir() async {
    setState(() {
      yukleniyor = true;
      hata       = "";
    });
    try {
      final response = await http
          .get(Uri.parse('$apiBaseUrl/cihaz-detaylari'))
          .timeout(const Duration(seconds: 60));
      if (response.statusCode == 200) {
        setState(() {
          cihazlar   = jsonDecode(response.body);
          yukleniyor = false;
        });
      } else {
        setState(() {
          hata       = "Sunucu hatası: ${response.statusCode}";
          yukleniyor = false;
        });
      }
    } catch (e) {
      setState(() {
        hata       = "Veri alınamadı: $e";
        yukleniyor = false;
      });
    }
  }

  IconData _ikonSec(String ikonAdi) {
    switch (ikonAdi) {
      case "kitchen":        return Icons.kitchen;
      case "electric_meter": return Icons.electric_meter;
      case "power":          return Icons.power;
      default:               return Icons.devices;
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
              icon: const Icon(Icons.refresh)),
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
                          child: const Text("Tekrar Dene")),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: cihazlar.length,
                  itemBuilder: (context, i) {
                    final item  = cihazlar[i];
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
                          style: const TextStyle(
                              fontWeight: FontWeight.bold),
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
                              color: aktif
                                  ? Colors.green.shade800
                                  : Colors.grey,
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
