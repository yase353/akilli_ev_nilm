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
  String durum = "Veri bekleniyor...";
  double anlikGuc = 0.0;
  double cosPhi = 1.0;
  double fatura = 0.0;
  bool yukleniyor = false;

  final String apiBaseUrl = "https://amaya-uncrystalled-nonusurpingly.ngrok-free.dev"; 

  Future<void> verileriGetir() async {
    setState(() => yukleniyor = true);
    try {
      // 🛡️ NGROK BYPASS HEADER EKLENDİ
      final response = await http.get(
        Uri.parse('$apiBaseUrl/ev-durumu'),
        headers: {"ngrok-skip-browser-warning": "true"},
      );
      
      if (response.statusCode == 200) {
        final veri = jsonDecode(response.body);
        setState(() {
          durum = veri['durum'];
          anlikGuc = (veri['anlik_guc_watt'] ?? 0.0).toDouble();
          cosPhi = (veri['cos_phi'] ?? 1.0).toDouble();
          fatura = (veri['tahmini_fatura_tl'] ?? 0.0).toDouble();
          yukleniyor = false;
        });
      }
    } catch (e) {
      setState(() {
        durum = "Bağlantı Hatası! Ngrok kapalı olabilir.";
        yukleniyor = false;
      });
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
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: yukleniyor
            ? const Center(child: CircularProgressIndicator())
            : Column(
                children: [
                  Card(
                    child: ListTile(
                      leading: Icon(durum == "Başarılı" ? Icons.check_circle : Icons.error, 
                                    color: durum == "Başarılı" ? Colors.green : Colors.red),
                      title: const Text("Sistem Durumu"),
                      subtitle: Text(durum),
                    ),
                  ),
                  const SizedBox(height: 10),
                  InkWell(
                    onTap: () => Navigator.push(context, MaterialPageRoute(builder: (context) => GrafikSayfasi(apiUrl: apiBaseUrl))),
                    child: Card(
                      color: Colors.orange.shade50,
                      child: ListTile(
                        leading: const Icon(Icons.electric_bolt, color: Colors.orange, size: 40),
                        title: const Text("Anlık Tüketim (Grafik)"),
                        subtitle: Text("$anlikGuc Watt\nCos φ: $cosPhi"),
                        trailing: const Icon(Icons.chevron_right),
                      ),
                    ),
                  ),
                  const SizedBox(height: 10),
                  InkWell(
                    onTap: () => Navigator.push(context, MaterialPageRoute(builder: (context) => CihazTabloSayfasi(apiUrl: apiBaseUrl))),
                    child: Card(
                      color: Colors.blue.shade50,
                      child: const ListTile(
                        leading: Icon(Icons.devices_other, color: Colors.blue, size: 40),
                        title: Text("Çalışan Cihaz Detayları"),
                        subtitle: Text("Tabloyu görmek için tıklayın"),
                        trailing: Icon(Icons.chevron_right),
                      ),
                    ),
                  ),
                  const SizedBox(height: 10),
                  Card(
                    color: Colors.green.shade50,
                    child: ListTile(
                      leading: const Icon(Icons.account_balance_wallet, color: Colors.green, size: 40),
                      title: const Text("Tahmini Aylık Fatura"),
                      subtitle: Text("$fatura TL", style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                    ),
                  ),
                ],
              ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: verileriGetir,
        child: const Icon(Icons.refresh),
      ),
    );
  }
}

class GrafikSayfasi extends StatelessWidget {
  final String apiUrl;
  const GrafikSayfasi({super.key, required this.apiUrl});

  Future<List<dynamic>> gecmisVeriGetir() async {
    // 🛡️ NGROK BYPASS HEADER EKLENDİ
    final response = await http.get(
      Uri.parse('$apiUrl/enerji-gecmisi'),
      headers: {"ngrok-skip-browser-warning": "true"},
    );
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
            spots.add(FlSpot(i.toDouble(), snapshot.data![i]['deger'].toDouble()));
          }
          return Padding(
            padding: const EdgeInsets.all(20),
            child: LineChart(
              LineChartData(
                lineBarsData: [
                  LineChartBarData(spots: spots, isCurved: true, color: Colors.orange, barWidth: 4),
                ],
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

  Future<List<dynamic>> cihazVeriGetir() async {
    // 🛡️ NGROK BYPASS HEADER EKLENDİ
    final response = await http.get(
      Uri.parse('$apiUrl/cihaz-detaylari'),
      headers: {"ngrok-skip-browser-warning": "true"},
    );
    return jsonDecode(response.body);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Cihaz Detay Tablosu")),
      body: FutureBuilder<List<dynamic>>(
        future: cihazVeriGetir(),
        builder: (context, snapshot) {
          if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
          return SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: DataTable(
              columns: const [
                DataColumn(label: Text('Cihaz')),
                DataColumn(label: Text('Tüketim')),
                DataColumn(label: Text('Maliyet')),
                DataColumn(label: Text('Durum')),
              ],
              rows: snapshot.data!.map((item) => DataRow(cells: [
                DataCell(Text(item['cihaz'].toString())),
                DataCell(Text(item['tuketim'].toString())),
                DataCell(Text(item['maliyet'].toString())),
                DataCell(Text(item['durum'].toString())),
              ])).toList(),
            ),
          );
        },
      ),
    );
  }
}