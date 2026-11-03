# Kanca Mini PC Gateway

Gateway ini mendukung beberapa sumber dalam satu mini PC: kamera RTSP, feed HLS publik dari DKI Jakarta dan domain CCTV pemerintah di DI Yogyakarta, satu topic MQTT, satu entity Home Assistant, endpoint HTTP JSON, Bluetooth LE, dan adapter kustom per sumber. Kamera mengirim frame JPEG berkala; audio dari stream kamera dapat diaktifkan secara eksplisit saat setup. Data sensor dikirim sebagai event JSON. Baseten API key, model, instruksi analisis, dan kebijakan tetap di server Kanca; mini PC hanya menyimpan token sumber dan kredensial perangkat.

Untuk demo kamera gudang, kamera staf, dan sensor suhu, pilih **Tambahkan 3 perangkat simulasi** di **Integrasi → Sumber perangkat**. Salin konfigurasi gateway yang ditampilkan dan simpan sebagai `config.json`. Contoh dengan placeholder tersedia di `gateway-config.simulator.example.json`; ganti URL Kanca, host simulator, ID, dan token. Nama sumber opsional ditampilkan di log gateway.

Untuk menggunakan dua kamera publik, pilih **Tambah 2 CCTV publik** di tempat yang sama. Paket ini memakai feed HLS publik Gatot Subroto dan Gerbang Pemuda dari [portal CCTV publik DKI Jakarta](https://jakcctv.jakarta.go.id/publik). Analisis gambar diaktifkan untuk sumber paket ini; cuplikan dikirim ke Baseten setiap 2 menit. Simpan konfigurasi gateway yang ditampilkan sebagai `config.json`, lalu mulai ulang gateway. Feed publik dapat berubah atau offline.

## Feed JSON publik

Di **Integrasi → Public Sources**, katalog menyediakan feed BMKG, Open-Meteo/USGS, serta 400 kamera publik: 200 feed di DI Yogyakarta dan 200 feed tambahan dari 11 wilayah Indonesia. Feed tambahan dipilih dari direktori PantauCCTV dan playlist HLS-nya diperiksa langsung sebelum dimasukkan. URL dapat berubah atau menjadi offline. Sumber baru dan otomasi dibuat **nonaktif**. Tombol **Get Data** mengambil satu pembaruan; permintaan data kamera lewat chat juga meminta cuplikan baru. Setelah respons itu, gateway berhenti membaca feed publik. Operator dapat mengaktifkan otomasi di kartu sumber dan memilih interval 5, 10, 30, atau 60 detik; feed kemudian diperiksa berkala sampai otomasi dimatikan. Analisis audio tetap nonaktif secara default. Sumber RTSP lokal dan integrasi yang tidak ditandai `on_demand` tetap memakai interval konfigurasi. Gateway mendukung sampai 512 sumber sekaligus dan otomatis memberi jeda 1,1 detik di antara permintaan BMKG supaya permintaan massal tetap di bawah batas API resmi 60 permintaan per menit per IP.

Salin konfigurasi yang ditampilkan ke `mini-pc-gateway/config.json` atau gabungkan isinya ke konfigurasi yang sudah ada. Sebelum menjalankan gateway, pastikan `server_url` adalah alamat HTTPS Kanca yang dapat dijangkau mini PC; ganti nilai URL jika alamat yang tampil di browser adalah `localhost` atau alamat lokal komputer lain. Jangan membagikan file konfigurasi karena berisi token ingest.

Gateway membaca feed dengan GET berkala, lalu mengirim objek JSON apa adanya sebagai `data.payload` ke sumber Kanca. BMKG memakai event `bmkg.earthquake.felt` untuk Gempa Dirasakan, `bmkg.earthquake.latest` untuk gempa terbaru, dan `bmkg.weather` untuk prakiraan. Bentuk feed Gempa Dirasakan mengikuti respons BMKG: daftar berada di `Infogempa.gempa`; setiap item dapat berisi `DateTime`, `Coordinates`, `Magnitude`, `Kedalaman`, `Wilayah`, dan `Dirasakan`. Contoh feed langsung tersedia di [API Gempa Dirasakan BMKG](https://data.bmkg.go.id/DataMKG/TEWS/gempadirasakan.json). Nilai dari BMKG seperti `Magnitude` dan `Kedalaman` berupa teks, sehingga jangan diasumsikan sebagai angka numerik tanpa konversi. Atribusikan data kepada BMKG.

Forecast BMKG per `adm4` berisi prakiraan tiga hari dengan resolusi tiga jam dan diperbarui dua kali sehari. Nama dan hierarki 100 lokasi di katalog diambil dari [dataset wilayah EMSIFA](https://www.emsifa.com/api-wilayah-indonesia/v2/) lalu setiap kode diperiksa terhadap endpoint prakiraan resmi BMKG sebelum ditambahkan; feed baru dipolling tiap jam. Cantumkan atribusi **BMKG (Badan Meteorologi, Klimatologi, dan Geofisika)** di produk yang menggunakan datanya. Lihat [dokumentasi Prakiraan Cuaca Terbuka BMKG](https://data.bmkg.go.id/prakiraan-cuaca/) untuk format field, kode adm4, serta batas akses terbaru.

Paket Open-Meteo menyediakan cuaca terkini Jakarta, Singapura, dan Tokyo; paket USGS menyediakan feed gempa signifikan 30 hari dan gempa 24 jam. Keduanya menggunakan HTTP JSON tanpa bearer token. Tiap paket publik dapat ditambahkan ke konfigurasi gateway yang sudah ada dengan menggabungkan entri sumber; jangan mengganti entri lama karena setiap sumber memiliki token sendiri. Feed publik dapat berubah, dibatasi, atau tidak tersedia sementara. Gateway tidak menyimpan antrean saat koneksi gagal.

## Persiapan di server Kanca

1. Jalankan versi Kanca terbaru. Di **Integrasi → Sumber perangkat**, buat sumber terpisah untuk tiap kamera, topic MQTT, atau entity Home Assistant. Simpan ID serta token masing-masing yang hanya ditampilkan sekali.
2. Untuk kamera pilih **Atur media**, aktifkan analisis gambar, isi pertanyaan yang sesuai seperti `Berapa dus yang terlihat di rak A? Jelaskan jika ada yang tertutup.`, dan simpan. Audio dinonaktifkan secara default; aktifkan hanya jika diperlukan dan diizinkan. MQTT dan Home Assistant tidak memerlukan analisis media.
3. Sediakan URL HTTPS yang dapat dijangkau mini PC, dengan TLS yang valid, menuju endpoint `POST /v1/ingest/{source_id}` dan `POST /v1/ingest/{source_id}/media`. Compose Kanca bawaan hanya mendengarkan di localhost, sehingga URL publik/jaringan **belum tersedia otomatis**. Gunakan reverse proxy yang hanya meneruskan endpoint ingest, memiliki batas ukuran dan rate limit, serta menolak semua route lain. Jangan mengekspos seluruh UI Kanca karena sesi UI lokal dibuat otomatis tanpa login.

Server memakai `BASETEN_API_KEY` dari environment server dan model `BASETEN_MEDIA_MODEL` (default `meta-models/muse-spark-open`). Media dikirim ke Baseten sebagai data URL dan tidak disimpan pada database Kanca; ringkasan dan hasil analisis disimpan sebagai event sumber. Provider dapat memiliki kebijakan retensi sendiri.

## Instalasi di mini PC

Prasyarat: Linux atau sistem dengan Docker Compose, Python 3, akses internet untuk feed HLS publik, akses ke stream RTSP lokal bila digunakan, dan URL HTTPS Kanca. Salin **folder `mini-pc-gateway` saja** ke mini PC; jangan menyalin `.env` server atau API key Baseten.

```bash
cd mini-pc-gateway
./start.sh
```

Saat setup pertama, gateway memeriksa OS/arsitektur, perangkat USB yang terdaftar di Linux, port serial, dan ketersediaan controller Bluetooth. Nama produk USB dapat menghasilkan **kandidat** protokol, tetapi tidak memastikan radio adalah coordinator yang cocok. Anda juga dapat menjalankan `python3 detect.py` kapan saja; hasil hanya ditampilkan secara lokal.

Pada penggunaan pertama, masukkan URL Kanca lalu pilih satu atau lebih sumber:

- **Kamera:** ID dan token sumber, URL RTSP atau feed HLS publik dari domain yang diizinkan (DKI Jakarta, Yogyakarta, Bantul, dan Gunungkidul), interval, dan pilihan audio.
- **MQTT:** ID dan token sumber, hostname dan port broker TLS, satu topic tanpa wildcard, serta kredensial broker bila diperlukan. Broker harus mempunyai sertifikat yang dipercaya sistem; pesan retained dilewati karena waktu pengukurannya tidak diketahui. Payload harus berupa objek JSON. Pengiriman best effort dan tidak ada antrean offline.
- **Home Assistant:** ID dan token sumber, URL Home Assistant, token akses, satu entity, dan interval. Setup mencoba menemukan dan menampilkan entity yang sudah tersedia di Home Assistant agar operator dapat memilihnya; jika hub tidak dapat diakses saat setup, ID bisa dimasukkan manual. Gunakan HTTPS atau jaringan lokal tepercaya untuk melindungi token. Perangkat Matter, Zigbee, Z-Wave, atau Bluetooth hanya dapat digunakan jika hub dan integrasi Home Assistant sudah mendukung dan menghubungkannya; gateway tidak melakukan pairing atau memasang driver sendiri. State `unknown` dan `unavailable` tidak dikirim; state numerik tersedia pada `data.value`.
- **HTTP JSON:** ID dan token sumber, URL endpoint yang menerima GET dan mengembalikan objek JSON, bearer token opsional, dan interval. Bearer token memerlukan HTTPS; redirect tidak diikuti. Respons diteruskan sebagai `http.json` dengan field `data.payload`. Endpoint dengan autentikasi atau format lain memerlukan adapter kustom.
- **Adapter kustom:** ID dan token sumber. Software lain menerjemahkan protokol perangkat menjadi satu objek JSON per baris, lalu dapat meneruskannya melalui `adapter_example.py`. Ini titik integrasi, bukan driver otomatis untuk semua protokol.
- **Bluetooth LE langsung:** setup menawarkan pemindaian lokal dan pemilihan perangkat, dengan input alamat manual sebagai fallback. Pilih characteristic yang bisa dibaca. Tersedia pembacaan level baterai standar atau characteristic mentah dalam `raw_hex`; format vendor tidak otomatis diterjemahkan. Membutuhkan mini PC Linux, radio Bluetooth, BlueZ dan system D-Bus. Gunakan `./scan-ble.sh` untuk memindai secara terpisah; pemindaian tidak memasangkan perangkat. Perangkat yang butuh pairing harus dipasangkan melalui OS terlebih dahulu. Akses D-Bus/BlueZ dan kompatibilitas characteristic bergantung pada konfigurasi mesin dan perangkat. Alamat BLE yang berubah secara acak mungkin tidak bisa digunakan untuk koneksi berulang.

Setelah menambahkan sumber, pilih `q` untuk menyelesaikan setup. Token dan URL kamera dimasukkan tersembunyi. `config.json` dibuat dengan izin `0600`, diabaikan Git, dan tidak disertakan dalam image. Pertahankan akses OS ke file tersebut hanya untuk operator tepercaya. Konfigurasi kamera lama tetap didukung. Feed publik mulai diambil setelah sumber aktif dan ada permintaan **Get Data**, pertanyaan kamera yang cocok di chat, atau otomasi yang diaktifkan di Integrasi. Untuk mengubah konfigurasi atau menambah sumber, hentikan gateway, simpan cadangan aman jika diperlukan, hapus `config.json`, lalu jalankan `./start.sh` lagi.

```bash
docker compose logs -f
./stop.sh
```

Contoh mengirim event dari adapter kustom ke sumber yang sudah didaftarkan di setup:

```bash
printf '%s\n' '{"temperature":29}' | docker compose exec -T gateway python adapter_example.py SOURCE_ID
```

Untuk Zigbee, Bluetooth, Z-Wave, atau Matter, salah satu jalur adalah menghubungkan perangkat ke hub atau Home Assistant yang mendukung perangkat tersebut, lalu pilih entity-nya saat setup. Perangkat dengan MQTT, HTTP, atau API vendor yang tidak sesuai format di atas memerlukan adapter tambahan. Gateway tidak dapat menemukan, memasangkan, atau mengendalikan semua perangkat secara otomatis.

Gateway otomatis restart melalui Docker, tetapi tidak menyimpan antrean data saat koneksi gagal dan tidak mencoba ulang cuplikan yang gagal. Interval adalah waktu jeda setelah rangkaian pengiriman selesai, sehingga waktu antarframe juga dipengaruhi durasi analisis. Kamera, broker, dan Home Assistant harus dapat dijangkau dari kontainer. URL RTSP bisa terlihat oleh administrator mesin melalui proses ffmpeg. Cuplikan sementara disimpan pada filesystem sementara kontainer dan dihapus setelah capture; kegagalan mendadak dapat menyisakan file hingga kontainer dihapus. Gunakan penyimpanan terenkripsi dan tata akses host sesuai kebutuhan.

## Hasil dan batas

Hasil muncul di **Integrasi → Lihat data** sebagai `media.vision` atau `media.audio`. Kanca hanya menyimpan teks ringkasan, jumlah opsional, dan indikator ketidakpastian. Pemantauan dengan task memeriksa event terbaru sesuai jadwalnya; buat task melalui chat setelah data pertama diterima. Hasil AI bersifat perkiraan: jika area terhalang, gelap, atau tidak pasti, jumlah bisa `null` dan tidak boleh dianggap sebagai stok yang terverifikasi.

Audio menangkap cuplikan lima detik dari stream yang sama, bukan transkripsi berkelanjutan. Gunakan hanya dengan pemberitahuan dan izin yang diperlukan. Gateway ini belum memiliki pairing QR, controller Zigbee/Z-Wave/Matter langsung, penemuan MQTT/Matter otomatis, antrean offline, atau kontrol perangkat. Bluetooth langsung belum diuji dengan radio dan perangkat fisik; koneksi kamera, broker MQTT, Home Assistant dan Baseten juga belum diuji langsung. Uji kompatibilitas dan kualitas data di lokasi sebelum penggunaan operasional.
