import 'dart:convert';
import 'dart:async'; // Zamanlayıcı için gerekli
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
  String durum = "Veri bekleniyor...";
  String anlikGuc = "0 W";
  String fatura = "0.0 TL";
  String aylikKwh = "0 kWh";
  bool yukleniyor = false;
  Timer? _timer; // Canlı akış için zamanlayıcı

  final String apiBaseUrl = "https://akilli-ev-nilm.onrender.com";

  Future<void> verileriGetir() async {
    // Otomatik yenilemede kullanıcıyı rahatsız etmemek için sadece ilk yüklemede veya manuel yenilemede loading gösteriyoruz
    try {
      final response = await http.get(
        Uri.parse('$apiBaseUrl/ev-durumu'),
        headers: {
          "ngrok-skip-browser-warning": "true",
          "Accept": "application/json"
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final veri = jsonDecode(response.body);
        setState(() {
          if (veri['durum'] == "Basarili") {
            anlikGuc = veri['anlik_toplam_watt'] ?? "0 W";
            fatura = veri['tahmini_fatura'] ?? "0.0 TL";
            aylikKwh = (veri['aylik_tuketim_kwh'] ?? "0") + " kWh";
            durum = "Başarılı";
          } else {
            anlikGuc = "0 W";
            fatura = "Cihaz Kapalı";
            aylikKwh = "0 kWh";
            durum = "Cihaz Çevrimdışı";
          }
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => durum = "Bağlantı Hatası!");
      }
    }
  }

  @override
  void initState() {
    super.initState();
    verileriGetir();
    // CANLI AKIŞ: Her 5 saniyede bir verileri güncelle
    _timer = Timer.periodic(const Duration(seconds: 5), (timer) {
      verileriGetir();
    });
  }

  @override
  void dispose() {
    _timer?.cancel(); // Sayfa kapanınca zamanlayıcıyı durdur
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Ev Enerji Takibi"),
        centerTitle: true,
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: RefreshIndicator(
        onRefresh: verileriGetir,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16.0),
          child: Column(
            children: [
              Card(
                elevation: 2,
                child: ListTile(
                  leading: Icon(
                    durum == "Başarılı" ? Icons.check_circle : Icons.error,
                    color: durum == "Başarılı" ? Colors.green : Colors.red,
                    size: 30,
                  ),
                  title: const Text("Sistem Durumu"),
                  subtitle: Text(durum, style: const TextStyle(fontWeight: FontWeight.bold)),
                ),
              ),
              const SizedBox(height: 15),
              InkWell(
                onTap: () => Navigator.push(context, MaterialPageRoute(builder: (context) => GrafikSayfasi(apiUrl: apiBaseUrl))),
                child: Card(
                  elevation: 4,
                  color: Colors.orange.shade50,
                  child: ListTile(
                    contentPadding: const EdgeInsets.symmetric(vertical: 10, horizontal: 16),
                    leading: const Icon(Icons.electric_bolt, color: Colors.orange, size: 50),
                    title: const Text("Tüketim Analizi (Grafik)", style: TextStyle(fontSize: 18)),
                    subtitle: Text("Anlık: $anlikGuc\nToplam: $aylikKwh", style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500)),
                    trailing: const Icon(Icons.show_chart, size: 30),
                  ),
                ),
              ),
              const SizedBox(height: 15),
              InkWell(
                onTap: () => Navigator.push(context, MaterialPageRoute(builder: (context) => CihazTabloSayfasi(apiUrl: apiBaseUrl))),
                child: Card(
                  elevation: 4,
                  color: Colors.blue.shade50,
                  child: const ListTile(
                    contentPadding: EdgeInsets.symmetric(vertical: 10, horizontal: 16),
                    leading: Icon(Icons.devices_other, color: Colors.blue, size: 50),
                    title: Text("Cihaz Detay Analizi", style: TextStyle(fontSize: 18)),
                    subtitle: Text("Priz bazlı detaylı tablo"),
                    trailing: Icon(Icons.table_rows, size: 30),
                  ),
                ),
              ),
              const SizedBox(height: 15),
              Card(
                elevation: 6,
                color: Colors.green.shade50,
                child: Padding(
                  padding: const EdgeInsets.all(20.0),
                  child: Column(
                    children: [
                      const Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.account_balance_wallet, color: Colors.green),
                          SizedBox(width: 10),
                          const Text("Tahmini Aylık Fatura", style: TextStyle(fontSize: 16)),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(fatura, style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.green)),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// --- GRAFİK SAYFASI (YIĞILMIŞ & ZAMAN SEÇİCİLİ) ---
class GrafikSayfasi extends StatefulWidget {
  final String apiUrl;
  const GrafikSayfasi({super.key, required this.apiUrl});

  @override
  State<GrafikSayfasi> createState() => _GrafikSayfasiState();
}

class _GrafikSayfasiState extends State<GrafikSayfasi> {
  int secilenSaat = 1;

  Future<List<dynamic>> gecmisVeriGetir() async {
    final response = await http.get(
      Uri.parse('${widget.apiUrl}/enerji-gecmisi?saat=$secilenSaat'),
      headers: {"ngrok-skip-browser-warning": "true"}
    );
    return jsonDecode(response.body);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Tüketim Analizi"),
        actions: [
          PopupMenuButton<int>(
            icon: const Icon(Icons.history),
            onSelected: (value) => setState(() => secilenSaat = value),
            itemBuilder: (context) => [
              const PopupMenuItem(value: 1, child: Text("Son 1 Saat")),
              const PopupMenuItem(value: 6, child: Text("Son 6 Saat")),
              const PopupMenuItem(value: 24, child: Text("Son 24 Saat")),
              const PopupMenuItem(value: 168, child: Text("Son 1 Hafta")),
            ],
          ),
        ],
      ),
      body: FutureBuilder<List<dynamic>>(
        future: gecmisVeriGetir(),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) return const Center(child: CircularProgressIndicator());
          if (snapshot.hasError || !snapshot.hasData || snapshot.data!.isEmpty) return const Center(child: Text("Veri bulunamadı."));

          List<FlSpot> spotsBuz = [];
          List<FlSpot> spotsEsp = [];
          List<FlSpot> spotsSeyyar = [];

          for (int i = 0; i < snapshot.data!.length; i++) {
            final v = snapshot.data![i];
            double x = i.toDouble();
            double b = (v['buzdolabi'] ?? 0.0).toDouble();
            double e = (v['esp32_ana'] ?? 0.0).toDouble();
            double s = (v['seyyar_priz'] ?? 0.0).toDouble();

            // Yığılmış (Stacked) grafik hesaplaması
            spotsBuz.add(FlSpot(x, b));
            spotsEsp.add(FlSpot(x, b + e));
            spotsSeyyar.add(FlSpot(x, b + e + s));
          }

          return Column(
            children: [
              Padding(
                padding: const EdgeInsets.all(16.0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _lejant("Buzdolabı", Colors.blue),
                    _lejant("ESP32 Ana", Colors.red),
                    _lejant("Seyyar", Colors.purple),
                  ],
                ),
              ),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(top: 20, right: 30, left: 10, bottom: 20),
                  child: LineChart(
                    LineChartData(
                      gridData: FlGridData(show: true, drawVerticalLine: false, horizontalInterval: 200),
                      titlesData: FlTitlesData(
                        show: true,
                        rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                        topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                        bottomTitles: AxisTitles(
                          axisNameWidget: Text("Son $secilenSaat Saatlik Veri Akışı"),
                          sideTitles: SideTitles(showTitles: true, interval: 10, reservedSize: 30),
                        ),
                        leftTitles: AxisTitles(
                          axisNameWidget: const Text("Güç (Watt)"),
                          sideTitles: SideTitles(showTitles: true, reservedSize: 45),
                        ),
                      ),
                      lineBarsData: [
                        _bar(spotsSeyyar, Colors.purple), // En üst (Toplam)
                        _bar(spotsEsp, Colors.red),     // Orta
                        _bar(spotsBuz, Colors.blue),     // En alt
                      ],
                    ),
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  LineChartBarData _bar(List<FlSpot> s, Color c) => LineChartBarData(
    spots: s,
    isCurved: true,
    color: c,
    barWidth: 3,
    dotData: const FlDotData(show: false),
    belowBarData: BarAreaData(show: true, color: c.withOpacity(0.4)),
  );

  Widget _lejant(String t, Color c) => Row(children: [Container(width: 12, height: 12, color: c), const SizedBox(width: 4), Text(t, style: const TextStyle(fontWeight: FontWeight.bold))]);
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
          if (snapshot.connectionState == ConnectionState.waiting) return const Center(child: CircularProgressIndicator());
          if (!snapshot.hasData || snapshot.data!.isEmpty) return const Center(child: Text("Veri yok."));

          return SingleChildScrollView(
            child: DataTable(
              headingRowColor: MaterialStateProperty.all(Colors.grey.shade200),
              columns: const [
                DataColumn(label: Text('Cihaz')),
                DataColumn(label: Text('Güç (W)')),
                DataColumn(label: Text('TL/Saat'))
              ],
              rows: snapshot.data!.map((item) => DataRow(cells: [
                DataCell(Text(item['cihaz'].toString())),
                DataCell(Text(item['tuketim'].toString())),
                DataCell(Text(item['saatlik_maliyet'].toString())),
              ])).toList(),
            ),
          );
        },
      ),
    );
  }
}
