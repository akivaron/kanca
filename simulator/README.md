# Simulator perangkat Kanca

Simulator lokal ini menyediakan dua kamera RTSP dan sensor suhu Home Assistant tanpa perangkat fisik. Docker Compose diperlukan.

## Perangkat simulasi

- Kamera Gudang: `rtsp://127.0.0.1:8554/kamera-gudang`, memakai gambar gudang demo.
- Kamera Area Staf: `rtsp://127.0.0.1:8554/kamera-staf`, memakai gambar area staf demo.
- Sensor Suhu: `http://127.0.0.1:8123`, entity `sensor.kanca_temperature`, nilai simulasi 24,5 °C dan token `simulator-token`.
- Broker MQTT TLS tetap tersedia di `127.0.0.1:8883`, topic contoh `kanca/sensor`.

Jalankan `./run.sh` untuk memulai; `./stop.sh` menghentikan semua layanan. Gambar RTSP adalah gambar demo yang di-loop, bukan kamera live. TLS MQTT memakai sertifikat self-signed.

## Sambungkan tiga perangkat ke Kanca

1. Buka **Integrasi → Sumber perangkat** lalu pilih **Tambahkan 3 perangkat simulasi**. Kanca membuat kartu Kamera Gudang, Kamera Area Staf, dan Sensor Suhu, lalu menampilkan konfigurasi gateway sekali.
2. Salin konfigurasi ke `mini-pc-gateway/config.json`. Ganti `YOUR_KANCA_URL` dan `YOUR_SIMULATOR_HOST` dengan alamat HTTPS Kanca serta host simulator yang dapat dijangkau gateway.
3. Pada kedua kartu kamera, buka **Atur media** dan aktifkan analisis gambar. Ini mengizinkan gateway mengirim cuplikan RTSP ke Kanca untuk dianalisis.
4. Jalankan simulator dengan `./run.sh`, lalu gateway dengan `cd mini-pc-gateway && ./start.sh`.

Contoh konfigurasi yang dapat diisi manual tersedia di `mini-pc-gateway/gateway-config.simulator.example.json`. Untuk gateway yang berjalan di Docker Compose pada host yang sama, `host.docker.internal` dapat dipakai sebagai host simulator; pastikan URL Kanca juga dapat dicapai dari container. Jangan gunakan token contoh di jaringan publik.
