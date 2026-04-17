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
  String durum = "Veri bekleniyor...";
  String anlikGuc = "0 W";
  String fatura = "0.0 TL";
  String aylikKwh = "0 kWh";
  bool yukleniyor = false;

  // Render URL'niz
  final String apiBaseUrl = "https://akilli-ev-nilm.onrender.com"; 

  Future<void> verileriGetir() async {
    setState(() => yukleniyor = true);
    try {
      final response = await http.get(
        Uri.parse('$apiBaseUrl/ev-durumu'),
        headers: {
          "ngrok-skip-browser-warning": "true", // Render uyarısını geçmek için şart
          "Accept": "application/json"
        },
      ).timeout(const Duration(seconds: 15));
      
      if (response.statusCode == 200) {
        final veri = jsonDecode(response.body);
        setState(() {
          if (veri['durum'] == "Basarili") {
            anlikGuc = veri['anlik_toplam_watt'] ?? "0 W";
            fatura = veri['tahmini_fatura'] ?? "0.0 TL";
            aylikKwh = (veri['aylik_tuketim_kwh'] ?? "0") + " kWh";
            durum = "Başarılı";
          } else {
            // Cihaz kapalıysa değerleri sıfırla
            anlikGuc = "0 W";
            fatura = "Cihaz Kapalı";
            aylikKwh = "0 kWh";
            durum = "Cihaz Çevrimdışı";
          }
          yukleniyor = false;
        });
      }
    } catch (e) {
      setState(() {
        durum = "Bağlantı Hatası!";
        anlikGuc = "0 W";
        fatura = "0.0 TL";
        yukleniyor = false;
      });
      print("Hata detay: $e");
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
              // SİSTEM DURUMU KARTI
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
              
              // GRAFİK KARTI (Tıklanabilir)
              InkWell(
                onTap: () => Navigator.push(context, MaterialPageRoute(builder: (context) => GrafikSayfasi(apiUrl: apiBaseUrl))),
                child: Card(
                  elevation: 4,
                  color: Colors.orange.shade50,
                  child: ListTile(
                    contentPadding: const EdgeInsets.symmetric(vertical: 10, horizontal: 16),
                    leading: const Icon(Icons.electric_bolt, color: Colors.orange, size: 50),
                    title: const Text("Anlık Toplam Güç", style: TextStyle(fontSize: 18)),
                    subtitle: Text("$anlikGuc\n$aylikKwh", style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500)),
                    trailing: const Icon(Icons.show_chart, size: 30),
                  ),
                ),
              ),
              const SizedBox(height: 15),
              
              // CİHAZ TABLO KARTI (Tıklanabilir)
              InkWell(
                onTap: () => Navigator.push(context, MaterialPageRoute(builder: (context) => CihazTabloSayfasi(apiUrl: apiBaseUrl))),
                child: Card(
                  elevation: 4,
                  color: Colors.blue.shade50,
                  child: const ListTile(
                    contentPadding: const EdgeInsets.symmetric(vertical: 10, horizontal: 16),
                    leading: Icon(Icons.devices_other, color: Colors.blue, size: 50),
                    title: Text("Cihaz Analizi", style: TextStyle(fontSize: 18)),
                    subtitle: Text("Priz bazlı detaylı tüketim tablosu"),
                    trailing: Icon(Icons.table_rows, size: 30),
                  ),
                ),
              ),
              const SizedBox(height: 15),
              
              // FATURA KARTI
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
                          Text("Tahmini Aylık Fatura", style: TextStyle(fontSize: 16)),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        fatura, 
                        style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.green)
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: verileriGetir,
        child: yukleniyor 
            ? const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2)) 
            : const Icon(Icons.refresh),
      ),
    );
  }
}

// --- GRAFİK SAYFASI ---
// --- GRAFİK SAYFASI (YENİLENMİŞ) ---
class GrafikSayfasi extends StatelessWidget {
  final String apiUrl;
  const GrafikSayfasi({super.key, required this.apiUrl});

  Future<List<dynamic>> gecmisVeriGetir() async {
    final response = await http.get(
      Uri.parse('$apiUrl/enerji-gecmisi'), 
      headers: {"ngrok-skip-browser-warning": "true"}
    );
    return jsonDecode(response.body);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Tüketim Analizi")),
      body: FutureBuilder<List<dynamic>>(
        future: gecmisVeriGetir(),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) return const Center(child: CircularProgressIndicator());
          if (snapshot.hasError || !snapshot.hasData || snapshot.data!.isEmpty) {
            return const Center(child: Text("Veri bulunamadı."));
          }

          List<FlSpot> spots = [];
          for (int i = 0; i < snapshot.data!.length; i++) {
            double deger = (snapshot.data![i]['deger'] ?? 0.0).toDouble();
            spots.add(FlSpot(i.toDouble(), deger));
          }

          return Column(
            children: [
              const Padding(
                padding: EdgeInsets.all(16.0),
                child: Text(
                  "Son 1 Saatlik Güç Değişimi (Watt)",
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.orange),
                ),
              ),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(top: 20, right: 30, left: 10, bottom: 20),
                  child: LineChart(
                    LineChartData(
                      gridData: FlGridData(
                        show: true,
                        drawVerticalLine: true,
                        horizontalInterval: 200, // Her 200W'da bir çizgi
                        getDrawingHorizontalLine: (value) => FlLine(color: Colors.grey.withOpacity(0.2), strokeWidth: 1),
                        getDrawingVerticalLine: (value) => FlLine(color: Colors.grey.withOpacity(0.2), strokeWidth: 1),
                      ),
                      titlesData: FlTitlesData(
                        show: true,
                        rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                        topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                        bottomTitles: AxisTitles(
                          axisNameWidget: const Text("Ölçüm Zamanı (Sıra)"),
                          sideTitles: SideTitles(
                            showTitles: true,
                            reservedSize: 30,
                            interval: 10, // Her 10 ölçümde bir sayı yaz
                            getTitlesWidget: (value, meta) => Text(value.toInt().toString(), style: const TextStyle(fontSize: 10)),
                          ),
                        ),
                        leftTitles: AxisTitles(
                          axisNameWidget: const Text("Güç (W)"),
                          sideTitles: SideTitles(
                            showTitles: true,
                            reservedSize: 45,
                            getTitlesWidget: (value, meta) => Text("${value.toInt()}W", style: const TextStyle(fontSize: 10)),
                          ),
                        ),
                      ),
                      borderData: FlBorderData(show: true, border: Border.all(color: Colors.grey.shade300)),
                      lineBarsData: [
                        LineChartBarData(
                          spots: spots, 
                          isCurved: true, 
                          color: Colors.orange, 
                          barWidth: 4, 
                          isStrokeCapRound: true,
                          dotData: const FlDotData(show: false),
                          belowBarData: BarAreaData(
                            show: true, 
                            color: Colors.orange.withOpacity(0.1)
                          ),
                        )
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
}

// --- TABLO SAYFASI ---
class CihazTabloSayfasi extends StatelessWidget {
  final String apiUrl;
  const CihazTabloSayfasi({super.key, required this.apiUrl});

  Future<List<dynamic>> cihazVeriGetir() async {
    final response = await http.get(
      Uri.parse('$apiUrl/cihaz-detaylari'), 
      headers: {"ngrok-skip-browser-warning": "true"}
    );
    return jsonDecode(response.body);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Cihaz Detay Analizi")),
      body: FutureBuilder<List<dynamic>>(
        future: cihazVeriGetir(),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) return const Center(child: CircularProgressIndicator());
          if (!snapshot.hasData || snapshot.data!.isEmpty) return const Center(child: Text("Cihaz verisi yok."));

          return SingleChildScrollView(
            scrollDirection: Axis.vertical,
            child: SizedBox(
              width: MediaQuery.of(context).size.width,
              child: DataTable(
                headingRowColor: MaterialStateProperty.all(Colors.blue.shade100),
                columns: const [
                  DataColumn(label: Text('Cihaz')),
                  DataColumn(label: Text('Güç (W)')),
                  DataColumn(label: Text('Maliyet/Saat')),
                ],
                rows: snapshot.data!.map((item) => DataRow(cells: [
                  DataCell(Text(item['cihaz'].toString())),
                  DataCell(Text(item['tuketim'].toString())),
                  DataCell(Text(item['saatlik_maliyet'].toString())),
                ])).toList(),
              ),
            ),
          );
        },
      ),
    );
  }
}
