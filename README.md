# Kanca — fondasi platform agent

Backend API-first untuk task agent lintas domain. Contoh connector bisnis dan perangkat menggunakan data dan tindakan **simulasi**. Lihat [PLAN.md](PLAN.md) untuk arah lengkap proyek.

## Menjalankan

Butuh Docker dan Docker Compose. Salin `.env.example` menjadi `.env`, ubah `KANCA_API_KEY` dan `POSTGRES_PASSWORD`, lalu:

```bash
./run.sh
```

Jalankan `./restart.sh` untuk membangun ulang image lalu restart API dan worker tanpa menghapus volume data. Untuk menghentikan layanan, jalankan `./stop.sh`. Lihat log menggunakan `docker compose logs -f`.

UI demo tersedia di `http://localhost:8765`, dokumentasi interaktif di `http://localhost:8765/docs`, health check di `http://localhost:8765/health`. Server menggunakan `KANCA_API_KEY` dari `.env` untuk sesi UI lokal; klien API eksternal tetap menggunakan header `X-API-Key`. PostgreSQL berjalan di jaringan internal Compose dan datanya disimpan dalam volume `kanca-postgres`.

### Data SQLite lama

PostgreSQL adalah database baru; data dari volume SQLite lama **tidak dipindahkan otomatis**. Untuk mempertahankan data sebelum menggunakan database baru, hentikan API dan worker, pastikan PostgreSQL aktif, lalu jalankan migrasi satu kali:

```bash
docker compose up -d db
docker compose stop api worker
docker compose build api
docker compose run --rm --no-deps api python -m app.migrate_sqlite /data/kanca.db
./run.sh
```

Migrasi membaca SQLite tanpa mengubahnya, mempertahankan ID dan cursor event, dan menolak PostgreSQL yang sudah berisi data. Jangan biarkan API, worker, atau proses lain menulis ke kedua database saat migrasi. Jika file SQLite berada di lokasi lain, sesuaikan path dalam kontainer. Periksa hasil sebelum menghapus volume lama; `./stop.sh` tidak menghapus volume.

`POSTGRES_PASSWORD` digunakan saat volume PostgreSQL pertama kali dibuat. Mengubahnya di `.env` setelah inisialisasi tidak otomatis mengubah password yang tersimpan. Gunakan karakter aman untuk URL pada password Compose.

Di UI, pilih connector simulasi, lalu kirim instruksi. Gunakan **Percakapan baru** untuk memisahkan topik dan sidebar untuk membuka riwayat. Dua belas pesan terakhir pada topik tersebut dikirim sebagai konteks saat model menyusun jawaban; setiap rencana yang dihasilkan menjadi task tersendiri. Rencana dari chat yang hanya membaca data atau memakai tindakan aman yang terdaftar dimulai otomatis; tindakan lain menunggu persetujuan. Saat ini tindakan aman terbatas pada pengingat simulasi dan pembuatan event eskalasi. Status diperbarui otomatis. Pembuatan task langsung melalui API/MCP dan rerun masih menunggu persetujuan. UI membuka sesi lokal otomatis; siapa pun yang dapat mengakses UI dapat mengakses data dan tindakan demo. Compose membatasi akses ke localhost; jangan mengekspos UI ke jaringan tanpa autentikasi pengguna yang sesuai. Jika menggunakan Docker, jalankan `./run.sh` kembali untuk membangun image setelah perubahan kode.

Menu **Tugas latar belakang** menampilkan task dari semua percakapan. Task baru dibuat melalui chat; jadwal task yang belum selesai bisa diubah dan harus disetujui ulang. Menghapus task dari daftar menghentikan task yang masih aktif dan mengarsipkannya; riwayat dan event tetap tersimpan. Task adalah pekerjaan yang dijalankan oleh worker bersama, bukan proses worker terpisah.

Gunakan **Jeda** untuk menangguhkan pemeriksaan berikutnya dan **Lanjutkan** untuk mengaktifkannya kembali. Progres dan tindakan yang sudah dilakukan tetap tersimpan. Jika jadwal sudah terlewat saat dilanjutkan, pemeriksaan berikutnya dapat langsung berjalan. Jeda tidak membatalkan pemeriksaan yang sudah mulai. Perubahan jadwal saat dijeda tetap membutuhkan persetujuan ulang. Integrasi API tersedia melalui `POST /v1/tasks/{id}/pause` dan `POST /v1/tasks/{id}/resume`.

Menu **Notifikasi** menampilkan hingga 100 pembaruan terbaru tentang persetujuan, penyelesaian, kegagalan, eskalasi, penghentian, jeda, dan kelanjutan tugas. Jenis notifikasi yang ditampilkan dapat dipilih; preferensinya tersimpan per tenant. Status baca tersimpan. Tugas yang selesai, gagal, atau dihentikan dapat dibuat ulang dari notifikasi, daftar tugas, atau chat. Rerun membuat task baru dari awal dan membutuhkan persetujuan lagi; riwayat task asli tetap ada. Notifikasi ini ditampilkan di aplikasi dan tersedia melalui API, bukan notifikasi push sistem operasi. Kematian proses worker itu sendiri belum dideteksi secara otomatis.

Menu **Integrasi → Sumber perangkat** memungkinkan pembuatan, pembaruan, penonaktifan, dan penghapusan sumber yang mengirim event JSON melalui HTTP. Tab **Public Sources** menyediakan 100 feed prakiraan BMKG per kelurahan/desa di 38 provinsi serta 400 feed CCTV publik. Feed publik default-nya tidak dipolling berkala: tombol **Get Data** atau permintaan data yang diarahkan AI di chat mengambil satu pembaruan; otomasi hanya berjalan setelah diaktifkan per sumber. Forecast BMKG berisi prakiraan tiga hari per tiga jam dan diperbarui dua kali sehari; API membatasi 60 permintaan per menit per IP dan mewajibkan atribusi BMKG. Simpan token saat sumber dibuat; hanya hash token disimpan oleh server. Contoh pengiriman dari mesin yang sama:

```bash
curl -X POST http://localhost:8765/v1/ingest/SOURCE_ID \
  -H 'Authorization: Bearer SOURCE_TOKEN' -H 'Content-Type: application/json' \
  -d '{"type":"temperature","data":{"value":29}}'
```

Event tersimpan dan dapat dilihat di UI serta menghasilkan event `source.event.v1` untuk subscriber. Sumber menyimpan `expected_interval_seconds` (default 300) untuk memperkirakan status penerimaan: menunggu data, terbaru, terlambat, atau nonaktif. Status ini hanya menunjukkan waktu event terakhir tiba; Kanca tidak memantau proses gateway secara langsung. Batas kesegaran untuk task adalah nilai yang lebih besar antara 5 menit dan dua kali interval yang diharapkan. UI menandai observasi yang lebih tua dari batas tersebut dan menandai hasil media yang tidak pasti. Sumber dihapus secara lunak agar riwayatnya tetap tersimpan. Ekspor event sumber tersedia di `/v1/sources/{id}/events/export`; ekspor event platform di `/v1/events/export`. Keduanya mendukung `format=json|csv`, maksimal 1.000 baris per permintaan, dan cursor `after` untuk melanjutkan ekspor. CSV mengamankan teks yang dapat dibaca spreadsheet sebagai formula. Aplikasi Compose hanya menerima koneksi localhost; perangkat lain membutuhkan gateway atau deployment yang aman dengan HTTPS. Streaming video, pairing QR/Bluetooth, dan kontrol perangkat belum tersedia. Jangan mengirim video atau foto melalui endpoint ini (batas 32 KiB).

Task yang disetujui dapat membaca event terbaru dari satu sumber aktif melalui `external.latest_event` dan memicu `external.escalate` sebagai event `task.escalated.v1` berdasarkan kondisi. UI Integrasi menyediakan pembuat aturan ambang dari field numerik yang sudah diterima; task yang dibuat tetap menunggu persetujuan dan menghasilkan eskalasi maksimal sekali per langkah. Data yang melewati batas kesegaran dinyatakan tidak dapat diverifikasi. Gunakan satu sumber Kanca per sensor atau entity agar pembacaan terbaru tidak tertimpa oleh perangkat lain. Event tidak secara otomatis membangunkan task: task memeriksa data sesuai jadwal yang disetujui. Eskalasi adalah event untuk consumer, bukan pesan yang dikirim langsung.

### Gateway perangkat

Contoh di `gateways/` berjalan terpisah dari API dan worker; dependensi opsional dipasang dengan `pip install -r gateways/requirements.txt`. Untuk masing-masing gateway, buat sumber di UI terlebih dahulu dan atur `KANCA_URL`, `KANCA_SOURCE_ID`, serta `KANCA_SOURCE_TOKEN` pada lingkungan gateway. Jalankan gateway di mesin yang bisa mengakses Kanca dan perangkat; jangan commit token. Jika koneksi lintas mesin, gunakan HTTPS dan gateway jaringan yang aman. Konfigurasi Compose bawaan tidak membuka port ke perangkat lain.

- **Home Assistant:** atur `HA_URL`, `HA_TOKEN`, dan `HA_ENTITIES` (contoh `sensor.suhu`), lalu jalankan `python gateways/home_assistant.py`. Gateway membaca state entity tiap 30 detik; `GATEWAY_INTERVAL` dapat diubah. Perangkat Matter yang sudah ditambahkan dan didukung Home Assistant dapat digunakan melalui entity yang tersedia di sana; Kanca tidak melakukan pairing Matter sendiri. State diteruskan sebagai string di `data.state`.
- **MQTT:** atur `MQTT_HOST`, `MQTT_TOPIC`, dan bila diperlukan `MQTT_USERNAME` serta `MQTT_PASSWORD`, lalu jalankan `python gateways/mqtt.py`. Broker harus menyediakan TLS terpercaya; port default `8883`. Pesan harus berupa objek JSON dan masuk di `data.payload`. Pengiriman gateway bersifat best effort, belum memiliki antrean lokal atau jaminan tidak ada kehilangan pesan.
- **Kamera:** atur `CAMERA_SOURCE` ke indeks kamera atau URL stream yang didukung OpenCV, lalu jalankan `python gateways/camera_motion.py`. Gateway hanya mengirim metadata perkiraan gerak, tidak mengirim frame, mengenali objek, atau memastikan paket aman. Gerakan bisa disebabkan perubahan cahaya; perlakukan sebagai sinyal untuk diperiksa.
- **ESP32:** `examples/esp32/kanca_sensor.ino` adalah contoh pengiriman bacaan dummy melalui HTTPS. Isi konfigurasi Wi-Fi, URL, token, dan sertifikat CA, lalu ganti nilai dummy dengan pembacaan sensor. Contoh belum diuji pada perangkat fisik.

Gateway ini belum diuji pada hub, broker, kamera, atau perangkat fisik, belum memiliki mekanisme pemulihan menyeluruh, dan tidak menyediakan kontrol perangkat. Gunakan untuk eksperimen lokal sebelum membangun deployment produksi. Untuk paket mini PC yang mengirim cuplikan gambar atau audio ke server Kanca untuk analisis Baseten, lihat [mini-pc-gateway/README.md](mini-pc-gateway/README.md).

Untuk menjalankan gateway dengan Docker di mesin yang sama dengan Kanca:

1. Buat sumber pada halaman **Sumber eksternal** dan simpan ID serta token yang ditampilkan sekali.
2. Salin salah satu contoh `gateways/home-assistant.env.example`, `gateways/mqtt.env.example`, atau `gateways/camera.env.example` ke `gateways/.env.home-assistant`, `gateways/.env.mqtt`, atau `gateways/.env.camera`. Isi ID, token, dan konfigurasi perangkat atau layanan yang sesuai. File tersebut diabaikan Git dan tidak disalin ke image.
3. Jalankan profil yang dipilih, contohnya:

   ```bash
   docker compose -f compose.yaml -f compose.gateways.yaml --profile home-assistant up -d --build
   ```

   Gunakan profil `mqtt` atau `camera` untuk gateway lainnya. Untuk kamera pada jaringan, `CAMERA_SOURCE` dapat berupa URL RTSP yang didukung OpenCV; perangkat USB memerlukan konfigurasi akses perangkat host yang sesuai dan belum disediakan otomatis. `./stop.sh` menghentikan seluruh profil gateway bersama Kanca.

Satu gateway Home Assistant dikonfigurasi untuk satu entity dan satu sumber Kanca. Nilai numerik disediakan sebagai `data.value`, sedangkan nilai asli tersedia sebagai `data.state`; `unknown` dan `unavailable` tidak diteruskan sebagai bacaan. MQTT melewati retained message karena waktu pengukurannya tidak dapat dipastikan. Kanca hanya mengenali struktur dari data yang sudah pernah diterima; kirim bacaan pertama sebelum meminta pemantauan. Menandai data sebagai baru berdasarkan waktu diterima tidak membuktikan bahwa perangkat atau hub mengukur ulang pada saat itu.

Frontend menggunakan React dan Vite di folder `frontend/`. Untuk development, jalankan API pada port 8765, lalu jalankan `npm install` dan `npm run dev` di folder `frontend/`. Vite meneruskan request `/v1` ke API. Untuk menyajikan frontend melalui FastAPI tanpa Docker, jalankan `npm run build` di folder tersebut terlebih dahulu.

Tanpa Docker: buat virtual environment, `pip install -r requirements.txt`, atur `KANCA_API_KEY` dan `DATABASE_URL` ke PostgreSQL, lalu jalankan `uvicorn app.main:app --reload --port 8765` dan `python -m app.worker` di terminal terpisah. Jika `DATABASE_URL` tidak diatur, SQLite melalui `KANCA_DB_PATH` masih tersedia untuk pengujian dan migrasi legacy.

## Contoh API

```bash
export KANCA_API_KEY='change-me'
curl -X POST http://localhost:8765/v1/connections \
  -H "X-API-Key: $KANCA_API_KEY" -H 'Content-Type: application/json' \
  -d '{"type":"device_demo"}'

curl -X POST http://localhost:8765/v1/tasks \
  -H "X-API-Key: $KANCA_API_KEY" -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: contoh-1' \
  -d '{"instruction":"Periksa suhu","explicit_steps":[{"capability":"device.read_temperature","arguments":{}}]}'
```

Ambil `id` dari respons, tinjau `plan`, lalu setujui versinya:

```bash
curl -X POST "http://localhost:8765/v1/tasks/TASK_ID/approve" \
  -H "X-API-Key: $KANCA_API_KEY" -H 'Content-Type: application/json' \
  -d '{"version":1}'
curl "http://localhost:8765/v1/tasks/TASK_ID" -H "X-API-Key: $KANCA_API_KEY"
curl "http://localhost:8765/v1/events" -H "X-API-Key: $KANCA_API_KEY"
```

Untuk mode model, set `BASETEN_API_KEY` dan kirim task tanpa `explicit_steps`. Muse Spark Open di Baseten mengusulkan capability dan jadwal; backend memvalidasi dan tetap meminta persetujuan. Model dapat dikonfigurasi dengan `BASETEN_MODEL`. Tanpa key, gunakan `explicit_steps`: ini mode demo, bukan AI. `examples/poll_events.py` menunjukkan konsumen eksternal yang membaca event dengan cursor; konsumen produksi harus menyimpan cursor dan ID event yang telah diproses.

## MCP untuk agent lain

Kanca menyediakan server MCP lokal melalui stdio. Tool yang tersedia mencakup daftar sumber dan koneksi, membaca event dan hasil task, bertanya dengan bahasa alami tentang observasi terbaru sumber (`ask_source`), membuat rancangan task, dan membuat rancangan rerun. Pertanyaan serta event terbaru yang diperlukan untuk menjawab dikirim ke Baseten. Jawaban sumber hanya memakai event yang sudah diterima dan analisis kamera yang sudah tersimpan; MCP tidak dapat meminta frame kamera baru. Rancangan task dan rerun tetap membutuhkan persetujuan pemilik di Kanca. Kontrol perangkat fisik secara langsung belum tersedia; setiap adapter kontrol harus menerbitkan aksi spesifik dan kebijakan persetujuannya sendiri.

Setelah `./run.sh`, MCP client yang mendukung stdio dapat menjalankan perintah berikut dari folder proyek:

```bash
docker compose exec -T -e KANCA_URL=http://api:8000 api python -m app.mcp_server
```

Perintah tersebut adalah proses MCP, bukan perintah interaktif untuk diketik lalu digunakan sebagai chat. Konfigurasikan command `docker` dan argumen `compose`, `exec`, `-T`, `-e`, `KANCA_URL=http://api:8000`, `api`, `python`, `-m`, `app.mcp_server` di MCP client. Jalankan dari folder proyek agar Compose menemukan konfigurasinya. API key digunakan dari environment container dan tidak dikirim melalui model. Akses ke proses dan API key memberi agent akses ke data akun demo ini; jangan bagikan akses tersebut sembarangan. Penggunaan dari host lain memerlukan transport dan autentikasi terpisah; endpoint MCP HTTP publik belum tersedia.

### Monitoring berulang

Task dapat menyertakan `schedule` seperti `{"interval_seconds":60,"max_runs":5}`. Pada langkah eksplisit, kondisi opsional menggunakan `{"step":0,"field":"temperature_c","operator":"gt","value":28}` untuk memeriksa hasil langkah sebelumnya. Operator tersedia: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`. Aksi hanya dilakukan sekali per langkah per task; hasil setiap pemeriksaan tersedia di `/v1/tasks/{id}/runs`. Semua connector saat ini simulasi.

### Webhook

Buat subscription dengan `POST /v1/webhook-subscriptions` dan body `{"url":"https://example.com/webhook"}`. Secret hanya dikembalikan saat dibuat; simpan di sisi penerima. Event dapat dibatasi lewat `event_types` saat membuat subscription atau `PUT /v1/webhook-subscriptions/{id}/event-types`; default `["*"]` berarti semua event. Event baru dibuat bersama delivery dalam transaksi yang sama. Worker mengirimnya dengan header `X-Kanca-Timestamp` dan `X-Kanca-Signature: sha256=<hex>`, menggunakan HMAC-SHA256 atas `timestamp + "." + raw_body`. Penerima harus memverifikasi signature, membatasi umur timestamp, dan melakukan deduplikasi berdasarkan ID event. Pengiriman at-least-once, dengan maksimal lima percobaan; lihat `/v1/webhook-deliveries`. Webhook hanya menerima HTTPS port 443 dan alamat IP publik; redirect tidak diikuti. Subscription hanya menerima event yang dibuat setelah subscription aktif dan cocok dengan filter.

## Kondisi dan batas saat ini

Ini MVP lokal, bukan implementasi lengkap dari PLAN.md. Compose menggunakan PostgreSQL; satu API key masih memetakan ke satu tenant. Webhook secret tersimpan dalam database; amankan volume dan gunakan TLS di depan API. Tidak ada LangGraph, Celery, pairing universal, SAM, atau tindakan nyata. Integrasi perangkat dan Baseten memerlukan pengujian langsung. Jangan gunakan untuk data atau tindakan produksi sampai autentikasi multi-tenant, penyimpanan secret, policy, dan recovery diperkuat.

## Tes

```bash
python -m pytest -q
```

Tes PostgreSQL tambahan dijalankan dengan `KANCA_TEST_DATABASE_URL` yang menunjuk ke database test dengan izin membuat dan menghapus schema. Jangan gunakan database produksi.
