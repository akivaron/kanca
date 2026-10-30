# Kanca Mini PC Gateway

Gateway ini mendukung beberapa sumber dalam satu mini PC: kamera RTSP, satu topic MQTT, satu entity Home Assistant, endpoint HTTP JSON, Bluetooth LE, dan adapter kustom per sumber. Kamera mengirim frame JPEG berkala; audio dari stream kamera dapat diaktifkan secara eksplisit saat setup. Data sensor dikirim sebagai event JSON. Baseten API key, model, instruksi analisis, dan kebijakan tetap di server Kanca; mini PC hanya menyimpan token sumber dan kredensial perangkat.

## Persiapan di server Kanca

1. Jalankan versi Kanca terbaru. Di **Integrasi → Sumber eksternal**, buat sumber terpisah untuk tiap kamera, topic MQTT, atau entity Home Assistant. Simpan ID serta token masing-masing yang hanya ditampilkan sekali.
2. Untuk kamera pilih **Atur media**, aktifkan analisis gambar, isi pertanyaan yang sesuai seperti `Berapa dus yang terlihat di rak A? Jelaskan jika ada yang tertutup.`, dan simpan. Audio dinonaktifkan secara default; aktifkan hanya jika diperlukan dan diizinkan. MQTT dan Home Assistant tidak memerlukan analisis media.
3. Sediakan URL HTTPS yang dapat dijangkau mini PC, dengan TLS yang valid, menuju endpoint `POST /v1/ingest/{source_id}` dan `POST /v1/ingest/{source_id}/media`. Compose Kanca bawaan hanya mendengarkan di localhost, sehingga URL publik/jaringan **belum tersedia otomatis**. Gunakan reverse proxy yang hanya meneruskan endpoint ingest, memiliki batas ukuran dan rate limit, serta menolak semua route lain. Jangan mengekspos seluruh UI Kanca karena sesi UI lokal dibuat otomatis tanpa login.

Server memakai `BASETEN_API_KEY` dari environment server dan model `BASETEN_MEDIA_MODEL` (default `meta-models/muse-spark-open`). Media dikirim ke Baseten sebagai data URL dan tidak disimpan pada database Kanca; ringkasan dan hasil analisis disimpan sebagai event sumber. Provider dapat memiliki kebijakan retensi sendiri.

## Instalasi di mini PC

Prasyarat: Linux atau sistem dengan Docker Compose, Python 3, akses ke stream RTSP kamera dan URL HTTPS Kanca. Salin **folder `mini-pc-gateway` saja** ke mini PC; jangan menyalin `.env` server atau API key Baseten.

```bash
cd mini-pc-gateway
./start.sh
```

Saat setup pertama, gateway memeriksa OS/arsitektur, perangkat USB yang terdaftar di Linux, port serial, dan ketersediaan controller Bluetooth. Nama produk USB dapat menghasilkan **kandidat** protokol, tetapi tidak memastikan radio adalah coordinator yang cocok. Anda juga dapat menjalankan `python3 detect.py` kapan saja; hasil hanya ditampilkan secara lokal.

Pada penggunaan pertama, masukkan URL Kanca lalu pilih satu atau lebih sumber:

- **Kamera:** ID dan token sumber, URL RTSP, interval, dan pilihan audio.
- **MQTT:** ID dan token sumber, hostname dan port broker TLS, satu topic tanpa wildcard, serta kredensial broker bila diperlukan. Broker harus mempunyai sertifikat yang dipercaya sistem; pesan retained dilewati karena waktu pengukurannya tidak diketahui. Payload harus berupa objek JSON. Pengiriman best effort dan tidak ada antrean offline.
- **Home Assistant:** ID dan token sumber, URL Home Assistant, token akses, satu entity, dan interval. Setup mencoba menemukan dan menampilkan entity yang sudah tersedia di Home Assistant agar operator dapat memilihnya; jika hub tidak dapat diakses saat setup, ID bisa dimasukkan manual. Gunakan HTTPS atau jaringan lokal tepercaya untuk melindungi token. Perangkat Matter, Zigbee, Z-Wave, atau Bluetooth hanya dapat digunakan jika hub dan integrasi Home Assistant sudah mendukung dan menghubungkannya; gateway tidak melakukan pairing atau memasang driver sendiri. State `unknown` dan `unavailable` tidak dikirim; state numerik tersedia pada `data.value`.
- **HTTP JSON:** ID dan token sumber, URL endpoint yang menerima GET dan mengembalikan objek JSON, bearer token opsional, dan interval. Bearer token memerlukan HTTPS; redirect tidak diikuti. Respons diteruskan sebagai `http.json` dengan field `data.payload`. Endpoint dengan autentikasi atau format lain memerlukan adapter kustom.
- **Adapter kustom:** ID dan token sumber. Software lain menerjemahkan protokol perangkat menjadi satu objek JSON per baris, lalu dapat meneruskannya melalui `adapter_example.py`. Ini titik integrasi, bukan driver otomatis untuk semua protokol.
- **Bluetooth LE langsung:** setup menawarkan pemindaian lokal dan pemilihan perangkat, dengan input alamat manual sebagai fallback. Pilih characteristic yang bisa dibaca. Tersedia pembacaan level baterai standar atau characteristic mentah dalam `raw_hex`; format vendor tidak otomatis diterjemahkan. Membutuhkan mini PC Linux, radio Bluetooth, BlueZ dan system D-Bus. Gunakan `./scan-ble.sh` untuk memindai secara terpisah; pemindaian tidak memasangkan perangkat. Perangkat yang butuh pairing harus dipasangkan melalui OS terlebih dahulu. Akses D-Bus/BlueZ dan kompatibilitas characteristic bergantung pada konfigurasi mesin dan perangkat. Alamat BLE yang berubah secara acak mungkin tidak bisa digunakan untuk koneksi berulang.

Setelah menambahkan sumber, pilih `q` untuk menyelesaikan setup. Token dan URL RTSP dimasukkan tersembunyi. `config.json` dibuat dengan izin `0600`, diabaikan Git, dan tidak disertakan dalam image. Pertahankan akses OS ke file tersebut hanya untuk operator tepercaya. Konfigurasi kamera lama tetap didukung. Untuk mengubah konfigurasi atau menambah sumber, hentikan gateway, simpan cadangan aman jika diperlukan, hapus `config.json`, lalu jalankan `./start.sh` lagi.

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
