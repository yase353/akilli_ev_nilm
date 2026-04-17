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
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.blueAccent),
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
  String durum = "Veri bekleniyor...";
  String anlikGuc = "0 W";
  String fatura = "0 TL";
  String aylikKwh = "0 kWh";
  bool yukleniyor = false;

  final String apiBaseUrl = "https://akilli-ev-nilm.onrender.com"; 

  Future<void> verileriGetir() async {
  try {
    final response = await http.get(Uri.parse('$apiBaseUrl/ev-durumu'));
    if (response.statusCode == 200) {
      final veri = jsonDecode(response.body);
      setState(() {
        anlikGuc = veri['anlik_toplam_watt'] ?? "0 W";
        fatura = veri['tahmini_fatura'] ?? "0.0 TL";
        aylikKwh = (veri['aylik_tuketim_kwh'] ?? "0") + " kWh";
        
        // Python'dan gelen duruma göre başlığı güncelle
        if (veri['durum'] == "Basarili") {
          durum = "Başarılı";
        } else {
          durum = "Cihaz Çevrimdışı";
        }
      });
    }
  } catch (e) {
    print("Hata: $e");
  }
}

  @override
  void initState() {
    super.initState();
    verileriGetir();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Ev Enerji Takibi"), centerTitle: true),
      body: RefreshIndicator(
        onRefresh: verileriGetir,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16.0),
          child: Column(
            children: [
              Card(
                child: ListTile(
                  leading: Icon(durum == "Başarılı" ? Icons.check_circle : Icons.error, color: durum == "Başarılı" ? Colors.green : Colors.red),
                  title: const Text("Sistem Durumu"),
                  subtitle: Text(durum),
                ),
              ),
              const SizedBox(height: 10),
              // GRAFİK KARTI
              InkWell(
                onTap: () => Navigator.push(context, MaterialPageRoute(builder: (context) => GrafikSayfasi(apiUrl: apiBaseUrl))),
                child: Card(
                  color: Colors.orange.shade50,
                  child: ListTile(
                    leading: const Icon(Icons.electric_bolt, color: Colors.orange, size: 40),
                    title: const Text("Anlık Tüketim (Grafik)"),
                    subtitle: Text("$anlikGuc\nAnaliz: $aylikKwh"),
                    trailing: const Icon(Icons.chevron_right),
                  ),
                ),
              ),
              const SizedBox(height: 10),
              // CİHAZ TABLOSU KARTI
              InkWell(
                onTap: () => Navigator.push(context, MaterialPageRoute(builder: (context) => CihazTabloSayfasi(apiUrl: apiBaseUrl))),
                child: Card(
                  color: Colors.blue.shade50,
                  child: const ListTile(
                    leading: Icon(Icons.devices_other, color: Colors.blue, size: 40),
                    title: Text("Cihaz Detay Tablosu"),
                    subtitle: Text("Priz bazlı tüketimler"),
                    trailing: Icon(Icons.chevron_right),
                  ),
                ),
              ),
              const SizedBox(height: 10),
              // FATURA KARTI
              Card(
                color: Colors.green.shade50,
                child: ListTile(
                  leading: const Icon(Icons.account_balance_wallet, color: Colors.green, size: 40),
                  title: const Text("Tahmini Aylık Fatura"),
                  subtitle: Text(fatura, style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: Colors.green)),
                ),
              ),
            ],
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: verileriGetir,
        child: yukleniyor ? const CircularProgressIndicator() : const Icon(Icons.refresh),
      ),
    );
  }
}

// --- GRAFİK SAYFASI ---
class GrafikSayfasi extends StatelessWidget {
  final String apiUrl;
  const GrafikSayfasi({super.key, required this.apiUrl});

  Future<List<dynamic>> gecmisVeriGetir() async {
    final response = await http.get(Uri.parse('$apiUrl/enerji-gecmisi'), headers: {"ngrok-skip-browser-warning": "true"});
    return jsonDecode(response.body);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Tüketim Grafiği")),
      body: FutureBuilder<List<dynamic>>(
        future: gecmisVeriGetir(),
        builder: (context, snapshot) {
          if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
          List<FlSpot> spots = [];
          for (int i = 0; i < snapshot.data!.length; i++) {
            spots.add(FlSpot(i.toDouble(), (snapshot.data![i]['deger'] ?? 0.0).toDouble()));
          }
          return Padding(
            padding: const EdgeInsets.all(20),
            child: LineChart(LineChartData(lineBarsData: [LineChartBarData(spots: spots, isCurved: true, color: Colors.orange, barWidth: 4)])),
          );
        },
      ),
    );
  }
}

// --- TABLO SAYFASI ---
class CihazTabloSayfasi extends StatelessWidget {
  final String apiUrl;
  const CihazTabloSayfasi({super.key, required this.apiUrl});

  Future<List<dynamic>> cihazVeriGetir() async {
    final response = await http.get(Uri.parse('$apiUrl/cihaz-detaylari'), headers: {"ngrok-skip-browser-warning": "true"});
    return jsonDecode(response.body);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Cihaz Analizi")),
      body: FutureBuilder<List<dynamic>>(
        future: cihazVeriGetir(),
        builder: (context, snapshot) {
          if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
          return SingleChildScrollView(
            child: DataTable(
              columns: const [DataColumn(label: Text('Cihaz')), DataColumn(label: Text('Güç')), DataColumn(label: Text('Maliyet'))],
              rows: snapshot.data!.map((item) => DataRow(cells: [
                DataCell(Text(item['cihaz'].toString())),
                DataCell(Text(item['tuketim'].toString())),
                // PYTHON KODUNDAKİ 'saatlik_maliyet' İLE EŞLEŞTİ:
                DataCell(Text(item['saatlik_maliyet'].toString())),
              ])).toList(),
            ),
          );
        },
      ),
    );
  }
}
