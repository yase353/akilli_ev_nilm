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

class EvDurumuSayfasi extends StatefulWidget {
  const EvDurumuSayfasi({super.key});

  @override
  State<EvDurumuSayfasi> createState() => _EvDurumuSayfasiState();
}

class _EvDurumuSayfasiState extends State<EvDurumuSayfasi> {
  // Veri değişkenleri
  String durum = "Bağlanıyor...";
  String anlikWatt = "0 W";
  String aktifCihaz = "Tespit Ediliyor...";
  String fatura = "0.0 TL";
  bool yukleniyor = false;
  Timer? _timer;

  // Render veya Ngrok URL'nizi buraya yazın
  final String apiBaseUrl = "https://amaya-uncrystalled-nonusurpingly.ngrok-free.dev"; 

  Future<void> verileriGetir() async {
    try {
      final response = await http.get(
        Uri.parse('$apiBaseUrl/ev-durumu'),
        headers: {"ngrok-skip-browser-warning": "true"},
      );
      
      if (response.statusCode == 200) {
        final veri = jsonDecode(response.body);
        setState(() {
          durum = veri['durum'];
          anlikWatt = veri['anlik_toplam_watt'];
          aktifCihaz = veri['aktif_cihaz'] ?? "Bilinmiyor";
          fatura = veri['tahmini_fatura'];
          yukleniyor = false;
        });
      }
    } catch (e) {
      setState(() {
        durum = "Bağlantı Hatası";
      });
    }
  }

  @override
  void initState() {
    super.initState();
    verileriGetir();
    // Her 5 saniyede bir verileri otomatik yenile (Canlı takip)
    _timer = Timer.periodic(const Duration(seconds: 5), (timer) => verileriGetir());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  // Yapay Zeka Tahmini için Görsel Widget
  Widget _buildAIPaneli() {
    IconData cihazIcon = Icons.psychology; // Varsayılan beyin ikonu
    Color iconColor = Colors.purple;

    if (aktifCihaz.contains("Ütü")) {
      cihazIcon = Icons.iron;
      iconColor = Colors.orange;
    } else if (aktifCihaz.contains("Televizyon")) {
      cihazIcon = Icons.tv;
      iconColor = Colors.blue;
    } else if (aktifCihaz.contains("Boşta")) {
      cihazIcon = Icons.power_settings_new;
      iconColor = Colors.grey;
    }

    return Card(
      elevation: 5,
      shadowColor: iconColor.withOpacity(0.3),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          gradient: LinearGradient(colors: [iconColor.withOpacity(0.1), Colors.white]),
        ),
        child: Row(
          children: [
            Icon(cihazIcon, size: 50, color: iconColor),
            const SizedBox(width: 20),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text("AI CANLI TESPİT", style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.grey)),
                  Text(aktifCihaz, style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: iconColor)),
                ],
              ),
            ),
            const CircularProgressIndicator(strokeWidth: 2, color: Colors.green),
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
          IconButton(onPressed: verileriGetir, icon: const Icon(Icons.refresh))
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            // Sistem Durum Şeridi
            Container(
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
              decoration: BoxDecoration(
                color: durum == "Basarili" ? Colors.green.shade100 : Colors.red.shade100,
                borderRadius: BorderRadius.circular(10)
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.circle, size: 10, color: durum == "Basarili" ? Colors.green : Colors.red),
                  const SizedBox(width: 8),
                  Text("Sistem: $durum", style: TextStyle(color: durum == "Basarili" ? Colors.green.shade900 : Colors.red.shade900)),
                ],
              ),
            ),
            const SizedBox(height: 20),
            
            // AI Paneli
            _buildAIPaneli(),
            
            const SizedBox(height: 20),

            // Anlık Güç Kartı
            InkWell(
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (context) => GrafikSayfasi(apiUrl: apiBaseUrl))),
              child: Card(
                child: ListTile(
                  leading: const Icon(Icons.electric_bolt, color: Colors.orange, size: 40),
                  title: const Text("Toplam Tüketim"),
                  subtitle: Text(anlikWatt, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
                  trailing: const Icon(Icons.show_chart, color: Colors.orange),
                ),
              ),
            ),

            const SizedBox(height: 10),

            // Fatura Kartı
            Card(
              color: Colors.green.shade50,
              child: ListTile(
                leading: const Icon(Icons.account_balance_wallet, color: Colors.green, size: 40),
                title: const Text("Tahmini Aylık Fatura"),
                subtitle: Text(fatura, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.green)),
              ),
            ),

            const SizedBox(height: 10),

            // Cihaz Detayları Butonu
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(minimumSize: const Size(double.infinity, 50)),
              onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (context) => CihazTabloSayfasi(apiUrl: apiBaseUrl))),
              icon: const Icon(Icons.list_alt),
              label: const Text("Tüm Cihaz Detaylarını Gör"),
            ),
          ],
        ),
      ),
    );
  }
}

// Grafik ve Tablo sayfaları (API yapılandırmasına uygun şekilde korunmuştur)
class GrafikSayfasi extends StatelessWidget {
  final String apiUrl;
  const GrafikSayfasi({super.key, required this.apiUrl});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Tüketim Analizi")),
      body: FutureBuilder<List<dynamic>>(
        future: http.get(Uri.parse('$apiUrl/enerji-gecmisi'), headers: {"ngrok-skip-browser-warning": "true"}).then((res) => jsonDecode(res.body)),
        builder: (context, snapshot) {
          if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
          List<FlSpot> spots = [];
          for (int i = 0; i < snapshot.data!.length; i++) {
            spots.add(FlSpot(i.toDouble(), (snapshot.data![i]['esp32_ana'] ?? 0).toDouble()));
          }
          return Padding(
            padding: const EdgeInsets.all(20),
            child: LineChart(
              LineChartData(
                lineBarsData: [LineChartBarData(spots: spots, isCurved: true, color: Colors.blue, barWidth: 3)],
                titlesData: const FlTitlesData(show: true),
              ),
            ),
          );
        },
      ),
    );
  }
}

class CihazTabloSayfasi extends StatelessWidget {
  final String apiUrl;
  const CihazTabloSayfasi({super.key, required this.apiUrl});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Cihaz Envanteri")),
      body: FutureBuilder<List<dynamic>>(
        future: http.get(Uri.parse('$apiUrl/cihaz-detaylari'), headers: {"ngrok-skip-browser-warning": "true"}).then((res) => jsonDecode(res.body)),
        builder: (context, snapshot) {
          if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
          return ListView.builder(
            itemCount: snapshot.data!.length,
            itemBuilder: (context, i) {
              final item = snapshot.data![i];
              return Card(
                margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: ListTile(
                  title: Text(item['cihaz']),
                  subtitle: Text("Tüketim: ${item['tuketim']} | Maliyet: ${item['saatlik_maliyet']}"),
                  trailing: Text(item['durum'], style: TextStyle(color: item['durum'] == "Aktif" ? Colors.green : Colors.grey)),
                ),
              );
            },
          );
        },
      ),
    );
  }
}
