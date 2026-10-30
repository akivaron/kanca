# Rencana proyek: platform agent yang dapat diintegrasikan

## Tujuan

Membangun backend untuk menjalankan tugas agent secara otonom, menyimpan progres dan hasilnya, serta menerbitkan event yang dapat digunakan oleh berbagai aplikasi. Kasus penggunaan pertama adalah pemantauan proses bisnis untuk pemilik usaha Indonesia, menggunakan data sintetis.

Platform ini menyediakan mekanisme umum untuk tugas, tools, persetujuan, dan event. Pengetahuan tentang pesanan, gudang, serta aturan bisnis ditempatkan dalam modul use case terpisah. Fleksibilitas tetap dibatasi oleh tools, data, dan izin yang benar-benar tersedia.

## Prinsip desain

- **API-first:** UI, chatbot, bot, dan integrasi pihak ketiga memakai kontrak backend yang sama.
- **Event-driven:** perubahan penting menghasilkan event yang dapat dikonsumsi secara independen dari UI.
- **Integrasi berbasis kemampuan:** connector mendaftarkan kemampuan yang dapat ditemukan agent tanpa memasukkan konsep domain ke core.
- **Otonomi dengan batas:** agent dapat memilih dan menjalankan langkah dalam cakupan yang telah diizinkan; perubahan cakupan dan tindakan berisiko memerlukan persetujuan.
- **Bisa pulih:** status tugas, langkah, dan hasil disimpan secara persisten; worker dapat melanjutkan setelah restart.
- **Dapat diaudit:** simpan tindakan, sumber bukti, hasil, kegagalan, dan hal yang tidak dapat diverifikasi.
- **Sederhana untuk MVP:** bangun modul dengan batas yang jelas dalam satu backend dan satu database; pisahkan layanan secara fisik hanya jika diperlukan.

## Tumpukan teknologi

| Komponen | Pilihan awal | Kegunaan |
| --- | --- | --- |
| API dan layanan inti | Python + FastAPI | API, otorisasi, manajemen tugas, dan kontrak integrasi. |
| Agent | Muse Spark melalui Meta Model API | Memahami instruksi, memilih tools, dan menyusun rencana serta laporan. |
| Orkestrasi agent | LangGraph | Mengelola langkah, state, dan jeda persetujuan; adapter model perlu diuji terhadap API Meta. |
| Validasi kontrak | Pydantic | Memvalidasi request, respons, argumen tools, dan payload event. |
| Penyimpanan | PostgreSQL | Menyimpan tugas, state, audit, outbox, dan konfigurasi subscriber. |
| Worker dan penjadwalan | Celery + Redis | Menjalankan tugas, pemeriksaan terjadwal, dan pengiriman event di latar belakang. |
| UI demo | Next.js + TypeScript | Chat, persetujuan, aktivitas, dan simulasi use case pertama. |
| Analisis visual | SAM 3.1 melalui Meta Model API | Menyediakan tool vision opsional untuk bukti foto. |
| Lingkungan lokal | Docker Compose | Menjalankan API, worker, scheduler, PostgreSQL, Redis, dan UI. |

Model, antrean, pengirim notifikasi, dan tools dibungkus melalui antarmuka internal supaya implementasinya dapat diganti. Tidak semua abstraksi perlu dibuat di awal: tambahkan adapter pada batas yang memang dipakai MVP.

## Arsitektur

```text
Chatbot / bot / aplikasi eksternal / UI demo
                    |
                    v
               FastAPI
                    |
          +---------+----------+
          |                    |
     Task service         Integrations API
          |                    |
          v                    v
  PostgreSQL <---------- Webhook subscriptions
  tasks / state / audit / events / outbox
          |
          v
  Celery worker + scheduler
          |
          +--> Agent runtime --> Muse Spark
          |         |
          |         +--> Capability / tool registry + policy enforcement
          |                    |
          |                    +--> Connector bisnis sintetis
          |                    +--> Connector perangkat sintetis
          |                    +--> Connector nyata di masa depan
          |
          +--> Event dispatcher --> webhook konsumen
```

Worker tidak mengirim pesan langsung ke UI atau chatbot. Worker mencatat perubahan status dan event; dispatcher mengantarkannya ke subscriber. UI dapat membaca status lewat API dan menggunakan mekanisme yang sama atau polling pada MVP.

## Model domain inti

- **Task:** tujuan, pemilik/tenant, status, cakupan, batas waktu, dan hasil akhir.
- **Task run dan step:** percobaan eksekusi, panggilan tool, hasil, error, dan waktu.
- **Approval:** rancangan yang menunggu keputusan, versi rencana, pihak yang menyetujui, dan waktu keputusan.
- **Tool:** kemampuan bernama dengan skema input/output, kategori risiko, dan implementasi yang dikontrol server.
- **Connector:** adapter yang menghubungkan sumber data, layanan, hub, atau perangkat ke antarmuka platform; memiliki siklus koneksi dan kesehatan sendiri.
- **Connection:** koneksi connector milik tenant, status autentikasi, cakupan akses, dan referensi kredensial yang disimpan secara aman.
- **Resource:** sumber daya yang ditemukan melalui connection, seperti perangkat, kelas, atau gudang. Core menyimpan identitas dan metadata umum tanpa bergantung pada atribut domain.
- **Capability:** kemampuan terstruktur yang ditawarkan resource, termasuk skema parameter dan hasil, jenis baca/tindakan/event, risiko, serta status ketersediaan. Agent hanya melihat kemampuan yang tersedia dan diizinkan.
- **Event:** fakta yang sudah terjadi, misalnya tugas selesai; memiliki ID dan versi skema.
- **Webhook subscription dan delivery:** tujuan pengiriman event dan status percobaan pengirimannya.
- **Audit record:** siapa atau apa yang melakukan tindakan, dasar keputusan, waktu, dan hasil.

Siklus status awal: `draft → awaiting_approval → scheduled / running → completed / failed / cancelled`. Tugas dapat menunggu input atau persetujuan baru, dan bisa dibatalkan. Perubahan status yang sah harus didefinisikan dan divalidasi di backend; `completed` berarti tugas selesai, sedangkan kesimpulan dapat tetap mencantumkan hal yang tidak terverifikasi.

## Alur utama

1. Klien membuat task dengan instruksi bahasa alami dan konteks yang diperlukan.
2. Agent menggunakan tools baca untuk memahami data dan menyusun rencana terstruktur. Jika konteks penting tidak tersedia, agent meminta klarifikasi.
3. API menyajikan rencana, cakupan, durasi, tools, serta tindakan yang diizinkan untuk disetujui.
4. Setelah disetujui, worker menjalankan atau menjadwalkan task. Agent menentukan urutan tools dalam cakupan itu; policy layer memvalidasi setiap panggilan secara independen dari model.
5. Pemeriksaan yang terjadwal menggunakan data terbaru. Pengingat simulasi dapat dilakukan secara otomatis jika diizinkan; tindakan di luar kewenangan menunggu persetujuan atau dieskalasikan.
6. Perubahan task, audit, dan event yang relevan disimpan. Event dispatcher mengirim event kepada subscriber.
7. Saat task selesai, hasil berisi apa yang diperiksa, bukti, tindakan, error, dan hal yang tidak dapat diverifikasi. Klien dapat mengambil detail lengkap melalui API.

## Kontrak API awal

Semua endpoint di bawah adalah rancangan awal di bawah `/v1`; detail skema akan difinalkan saat implementasi dan didokumentasikan melalui OpenAPI.

| Method | Endpoint | Kegunaan |
| --- | --- | --- |
| POST | `/tasks` | Membuat tugas dari instruksi dan konteks. |
| GET | `/tasks/{id}` | Mengambil status, rencana, dan hasil. |
| POST | `/tasks/{id}/messages` | Memberi klarifikasi atau instruksi lanjutan. |
| POST | `/tasks/{id}/approve` | Menyetujui versi rencana tertentu. |
| POST | `/tasks/{id}/cancel` | Membatalkan pekerjaan yang masih dapat dibatalkan. |
| GET | `/tasks/{id}/events` | Melihat riwayat event task. |
| GET | `/tasks/{id}/audit` | Melihat jejak aktivitas berdasarkan izin akses. |
| POST / GET | `/webhook-subscriptions` | Membuat dan melihat subscription. |
| PATCH / DELETE | `/webhook-subscriptions/{id}` | Mengubah atau menonaktifkan subscription. |
| GET | `/webhook-deliveries` | Memeriksa status delivery untuk troubleshooting. |
| GET | `/connector-types` | Melihat connector dan metode onboarding yang tersedia. |
| POST / GET | `/connections` | Memulai koneksi atau melihat koneksi milik tenant. |
| GET / DELETE | `/connections/{id}` | Melihat status atau mencabut koneksi. |
| GET | `/connections/{id}/resources` | Melihat resource dan capability yang ditemukan. |

Gunakan `Idempotency-Key` untuk pembuatan task dan operasi lain yang dapat menyebabkan efek samping. API mengembalikan ID task dan status saat ini; penyelesaian task tidak perlu menunggu dalam satu HTTP request.

## Discovery, pairing, dan connector

Tujuannya adalah pengalaman integrasi yang mudah: pengguna memilih sumber, menyelesaikan pairing atau login yang diperlukan, meninjau izin, lalu agent dapat menggunakan kemampuan yang terdaftar secara otonom dalam batas persetujuan. Metode discovery bergantung pada connector: QR, Bluetooth, jaringan lokal, atau autentikasi ke layanan. Menemukan sebuah perangkat tidak berarti platform sudah dapat mengontrolnya: protokol yang kompatibel, adapter, dan otorisasi tetap diperlukan.

Alur umum:

1. Klien meminta memulai connection untuk connector tertentu; respons menyediakan status dan langkah onboarding yang diperlukan.
2. Pengguna menyelesaikan scan QR, pairing, login, atau konfirmasi yang disyaratkan oleh perangkat atau layanan. Jangan menyimpan kode pairing atau kredensial pada audit atau event.
3. Connector memverifikasi koneksi, menemukan resource dan kemampuannya, lalu mendaftarkan skema yang divalidasi ke registry.
4. Pengguna meninjau cakupan akses dan tindakan yang boleh diusulkan atau dijalankan. Connection yang aktif tidak otomatis menyetujui semua tindakan agent.
5. Agent menemukan capability yang sesuai dengan instruksi, menyusun rencana, dan meminta persetujuan sesuai policy. Pemanggilan capability divalidasi lagi ketika dieksekusi.
6. Connector melaporkan perubahan ketersediaan dan error; pengguna dapat mencabut koneksi. Pencabutan menghentikan penggunaan capability terkait dan memperbarui task yang terdampak.

Capability memiliki nama dan versi, deskripsi, skema input/output, risiko, cakupan resource, serta informasi ketersediaan. Adapter memetakan capability ke protokol domain; logika gudang, smart home, dan edukasi berada di connector atau modul domain, bukan di core. Metadata yang berasal dari perangkat atau layanan eksternal tidak boleh diperlakukan sebagai instruksi untuk melewati policy.

Connector pertama adalah **bisnis sintetis** dan **perangkat sintetis** (sensor suhu dan lampu). Kedua connector ini menguji bahwa mekanisme yang sama dapat melayani domain berbeda. Integrasi perangkat nyata menyusul, dengan Matter atau Home Assistant sebagai kandidat awal sesuai perangkat yang dipilih. Sistem tidak menjanjikan kompatibilitas universal: beberapa perangkat memerlukan hub, aplikasi vendor, atau konektor khusus.

Server cloud tidak otomatis dapat mengakses Bluetooth atau jaringan lokal pengguna. Jika dibutuhkan, sediakan gateway lokal atau gunakan hub/layanan yang diizinkan; autentikasi gateway dan batas aksesnya menjadi bagian dari desain connector. Web UI, aplikasi mobile, dan developer eksternal dapat menggunakan API onboarding yang sama, tetapi scan Bluetooth atau QR membutuhkan kemampuan dan izin pada perangkat klien yang mendukungnya.

Status connection awal: `pending → awaiting_user → connected`, dengan `failed`, `disconnected`, dan `revoked` untuk kondisi yang sesuai. Komunikasikan kapan pengguna perlu melakukan tindakan; jangan mengklaim pairing berhasil sebelum connector memverifikasinya.

### Pemantauan kamera sebagai connector

Camera processor merupakan producer event terpisah: membaca video simulasi atau sumber yang didukung, menghasilkan kejadian dan referensi bukti, lalu mengirimkannya ke platform. Core menerima event umum tanpa bergantung pada domain gudang. Connector kamera nyata, protokol, dan gateway dipilih berdasarkan perangkat yang akan didukung.

Gunakan frame atau cuplikan yang relevan sesuai kebutuhan, dengan kebijakan penyimpanan dan akses bukti. Identitas paket atau pesanan memerlukan bukti penghubung seperti barcode atau scan; jika tidak tersedia, hasilnya tidak terverifikasi. Use case awal memantau proses dan area, bukan identifikasi wajah atau penilaian individu.

## Event dan integrasi notifikasi

Event menggambarkan fakta, sedangkan notifikasi adalah keputusan konsumen untuk menyampaikan fakta itu melalui kanal tertentu. Satu event dapat dipakai banyak subscriber: misalnya bot WhatsApp, chatbot lain, dashboard, atau sistem internal. Integrasi ke kanal nyata tidak termasuk MVP kecuali ditambahkan secara khusus.

Event awal:

- `task.created.v1`
- `task.approval_requested.v1`
- `task.started.v1`
- `task.action_taken.v1`
- `task.escalated.v1`
- `task.completed.v1`
- `task.failed.v1`
- `task.cancelled.v1`

Contoh envelope:

```json
{
  "id": "evt_01_example",
  "type": "task.completed.v1",
  "occurred_at": "2026-10-29T10:00:00Z",
  "tenant_id": "tenant_demo",
  "task_id": "task_01_example",
  "data": {
    "status": "completed",
    "summary": "12 pesanan diperiksa; satu perlu ditindaklanjuti.",
    "result_url": "/v1/tasks/task_01_example"
  }
}
```

Kontrak delivery:

- **Transactional outbox:** perubahan status dan event disimpan dalam transaksi database yang sama agar event tidak hilang di antara penyimpanan hasil dan pengiriman.
- **At-least-once:** delivery dapat terjadi lebih dari sekali. Konsumen wajib melakukan deduplikasi berdasarkan `id` event; sistem tidak menjanjikan exactly-once.
- **Retry:** ulangi delivery gagal dengan backoff dan batas percobaan; setelah itu tandai gagal untuk diperiksa atau dikirim ulang secara terkontrol.
- **Verifikasi:** tanda tangani webhook dengan secret per subscription dan timestamp; konsumen memverifikasi signature dan membatasi replay. Jangan mengekspos secret dalam respons setelah dibuat.
- **Isolasi:** hanya kirim event ke subscription milik tenant yang relevan dan sesuai filter jenis event. Validasi tujuan webhook untuk mengurangi risiko SSRF, termasuk alamat internal dan redirect.
- **Urutan:** waktu dan urutan delivery tidak dijamin; konsumen mengambil status terkini dari API jika perlu. Payload hanya berisi informasi minimum; akses detail tetap memerlukan autentikasi.
- **Observabilitas:** simpan status, jumlah percobaan, waktu, dan respons yang aman untuk dicatat pada setiap delivery.

Untuk MVP, webhook adalah mekanisme push pertama. Endpoint riwayat event mendukung polling dan debugging. SSE atau broker publik dapat ditambahkan jika ada kebutuhan nyata; keduanya tidak perlu dibangun bersamaan pada tahap awal.

## Keamanan dan batas agent

- Identitas dan tenant harus ditentukan dari kredensial server-side, bukan dipercaya dari input model atau payload klien.
- Akses tiap task, tool, dan subscription dibatasi berdasarkan tenant dan izin pemanggil.
- Tool registry memakai skema yang tervalidasi dan daftar kemampuan yang disetujui. Agent tidak menjalankan kode, SQL, URL, atau shell bebas yang dihasilkan model.
- Tools berisiko memerlukan persetujuan yang sesuai dengan versi rencana dan tindakan. Batasi durasi, frekuensi, jumlah tindakan, dan cakupan sumber daya.
- Konten dari dokumen, foto, tool, dan pesan eksternal diperlakukan sebagai data yang tidak tepercaya, bukan instruksi yang dapat mengubah policy.
- Kredensial connector dan kode pairing tidak diberikan kepada model; simpan sebagai secret dengan kontrol akses dan dukung pencabutan. Discovery tidak memberi izin kontrol secara otomatis.
- Catat tindakan berhasil, ditolak, atau gagal; jangan mencatat secret. Pengingat simulasi dan tindakan nyata harus dibedakan jelas.
- Simpan waktu dalam UTC dan tampilkan zona waktu bisnis secara eksplisit; tanggal ambigu memerlukan klarifikasi.

## Use case pertama: pemilik bisnis

Gunakan data sintetis gudang, pesanan, jadwal pickup, status packing, dan bukti foto. Tools baca mengakses data tersebut; aturan pemantauan awal mencakup keterlambatan packing dan selisih jumlah. Agent dapat menyusun kombinasi pemeriksaan sesuai permintaan, selama tools dan data mendukungnya.

Tindakan pertama adalah pengingat simulasi dan eskalasi. Event `task.completed.v1` dikirim ke webhook contoh yang menampilkan payload, sehingga dapat dibuktikan bahwa konsumen tidak perlu memakai UI bawaan.

SAM 3.1 ditambahkan setelah alur inti bekerja. Hasil segmentasi dapat mendukung pemeriksaan objek yang terlihat, tetapi foto buram, objek tertutup, atau paket tertutup menghasilkan status tidak terverifikasi; deteksi visual bukan bukti pasti isi dan SKU.

## Tahapan implementasi

1. **Fondasi:** struktur repo, konfigurasi, Docker Compose, FastAPI, PostgreSQL, migrasi, health check, dan data sintetis.
2. **Task dan approval:** API task, state machine, audit, otorisasi dasar, serta persetujuan yang terikat ke versi rencana.
3. **Agent dan tools:** integrasi Muse Spark, capability/tool registry, policy layer, state persisten, dan penanganan klarifikasi. Buat connector bisnis sintetis dan connector perangkat sintetis untuk membuktikan core tidak bergantung pada bisnis. Sediakan adapter demo tanpa API key yang diberi label jelas; jangan menyebutnya model sungguhan.
4. **Background execution:** Celery/Redis, jadwal pemeriksaan, pemulihan, pembatalan, dan pencegahan tindakan ganda.
5. **Event dan webhook:** transactional outbox, subscription, penandatanganan, retry, delivery log, dan contoh konsumen yang melakukan deduplikasi.
6. **UI demo:** chat, persetujuan, timeline, hasil, dan inbox simulasi menggunakan API publik yang sama.
7. **Vision opsional:** integrasi SAM dan skenario foto sintetis, setelah alur utama tervalidasi.
8. **Integrasi nyata:** pilih perangkat dan protokol yang spesifik, lalu implementasikan discovery, pairing, gateway bila diperlukan, siklus pencabutan, dan pengujian pada perangkat yang didukung. Tambahkan camera processor nyata hanya setelah sumber dan kebutuhan bukti ditetapkan.

## Kriteria penerimaan MVP

- Developer dapat membuat task dan menyetujui rencana melalui API tanpa menggunakan UI.
- Setelah approval, worker melanjutkan task di latar belakang dan hasil tetap tersedia setelah restart.
- Setidaknya dua instruksi bahasa alami yang berbeda dapat menggunakan tools yang sama dalam kombinasi yang berbeda; permintaan di luar kemampuan mendapat respons yang jujur.
- Connector bisnis dan perangkat sintetis terdaftar melalui kontrak yang sama; task nonbisnis dapat menemukan dan memakai capability tanpa mengubah core. Tes memastikan core tidak bergantung pada model atau istilah domain bisnis.
- Koneksi simulasi dapat dibuat, dilihat, dan dicabut; pencabutan mencegah pemanggilan capability terkait. Pairing fisik belum menjadi klaim penerimaan MVP.
- Aksi yang belum disetujui ditolak oleh backend, dan retry tidak menggandakan pengingat simulasi.
- Penyelesaian task menghasilkan event yang diterima webhook contoh; delivery duplikat dapat dideduplikasi konsumen.
- Kegagalan delivery terlihat dan dicoba ulang sesuai kebijakan; kegagalan integrasi tidak mengubah hasil task menjadi berhasil palsu.
- Laporan dan audit menyatakan apa yang diperiksa dan apa yang tidak dapat diverifikasi.
- Dokumentasi mencakup setup lokal, konfigurasi Meta API, OpenAPI, contoh pembuatan task, dan contoh validasi signature webhook.

## Pertanyaan desain yang bisa diputuskan saat implementasi

- Apakah MVP menggunakan satu API key per tenant atau penyedia identitas eksternal? Mulai dengan identitas sederhana yang tetap mengisolasi tenant.
- Berapa lama event dan delivery log disimpan? Tentukan kebijakan retensi sebelum penggunaan dengan data nyata.
- Apakah integrasi pertama cukup menerima webhook, atau perlu mengirim balasan melalui API task? Kontrak di atas mendukung keduanya.
- Batas pemantauan, jumlah retry, dan timeout disediakan sebagai konfigurasi dengan default yang terdokumentasi.
