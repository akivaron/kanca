import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import warehouseDemo from './assets/gudang-demo.webp';
import staffCameraDemo from './assets/staff-camera-demo.webp';

const publicCctvFeeds = {
  'CCTV Publik Gatot Subroto': 'https://dki-jkt.balitower.co.id:7028/502045_JKP_POLDA_JPO-JL.-GATOT-SUBROTO-7_CCTV-01/embed.html',
  'CCTV Publik Gerbang Pemuda': 'https://dki-jkt.balitower.co.id:7028/502160_JKP_POLDA_JL.-GERBANG-PEMUDA-C03_CCTV-01/embed.html',
};

const LanguageContext = createContext(null);
const englishTranslations = new Map([
  ["Menu utama", "Main menu"],
  ["Dashboard", "Dashboard"],
  ["Chat baru", "New chat"],
  ["Bersihkan riwayat", "Clear history"],
  ["Bersihkan riwayat percakapan?", "Clear conversation history?"],
  ["Semua percakapan akan dihapus dari daftar riwayat. Tugas yang sudah dibuat tetap berjalan dan tersedia di Tugas latar belakang.", "All conversations will be removed from history. Existing tasks will keep running and remain available under Background tasks."],
  ["Tugas", "Task"],
  ["Daftar tugas", "Tasks"],
  ["Integrasi", "Integrations"],
  ["Riwayat percakapan", "Conversation history"],
  ["Draft", "Drafts"],
  ["Percakapan", "Conversations"],
  ["Kembalikan", "Restore"],
  ["Pindah ke draft", "Move to drafts"],
  ["Hapus", "Delete"],
  ["Dokumentasi API ↗", "API documentation ↗"],
  ["Ruang percakapan", "Chat room"],
  ["Tugas latar belakang", "Background tasks"],
  ["Notifikasi", "Notifications"],
  ["Sumber eksternal", "External sources"],
  ["Pantau perangkat dan lanjutkan percakapan", "Monitor devices and continue your conversation"],
  ["Kelola pemantauanmu di satu tempat", "Manage monitoring in one place"],
  ["Pembaruan tugasmu", "Task updates"],
  ["Kelola perangkat dan layanan", "Manage devices and services"],
  ["Tempat untuk mendelegasikan tugasmu", "A place to delegate work"],
  ["Terhubung", "Connected"],
  ["Belum terhubung", "Not connected"],
  ["Aktifkan mode terang", "Switch to light mode"],
  ["Aktifkan mode gelap", "Switch to dark mode"],
  ["Mode terang", "Light mode"],
  ["Mode gelap", "Dark mode"],
  ["Switch to English", "Ganti ke Bahasa Indonesia"],
  ["Switch to Indonesian", "Switch to English"],
  ["Navigasi utama", "Main navigation"],
  ["RUANG KENDALI", "OPERATIONS AT A GLANCE"],
  ["Pantau aktivitas. Jaga semuanya bergerak.", "Keep an eye on what matters."],
  ["Perangkat, pemeriksaan, dan aktivitas Kanca dalam satu ruang kendali. Mulai pemeriksaan dari instruksi di bawah.", "Devices, checks, and Kanca activity in one control room. Start a check with the prompt below."],
  ["RINGKASAN AKTIVITAS", "OPERATIONS OVERVIEW"],
  ["Selamat datang di Kanca ✳", "Welcome to Kanca ✳"],
  ["Halo, ada yang bisa aku bantu hari ini?", "What would you like to keep an eye on?"],
  ["Beritahu apa yang ingin kamu pantau. Pemeriksaan dan tindakan aman langsung berjalan; tindakan berisiko menunggu persetujuanmu.", "Tell Kanca what to monitor. Safe checks run automatically; higher risk actions wait for your approval."],
  ["Periksa suhu ruangan", "Check room temperature"],
  ["Periksa pesanan", "Check orders"],
  ["Pantau pesanan", "Monitor orders"],
  ["Belum ada aktivitas di percakapan ini. Mulai pemeriksaan dari instruksi di bawah.", "No activity in this conversation yet. Start a check with the prompt below."],
  ["Ceritakan apa yang ingin kamu lakukan...", "Describe what you want Kanca to monitor..."],
  ["Instruksi untuk Kanca", "Instructions for Kanca"],
  ["Enter untuk kirim · Shift + Enter untuk baris baru", "Press Enter to send · Shift + Enter for a new line"],
  ["Kanca dapat membuat kesalahan. Periksa rencana sebelum menyetujui.", "Kanca can make mistakes. Review plans before approving them."],
  ["Kamu", "You"],
  ["Kanca", "Kanca"],
  ["Kanca sedang mengetik", "Kanca is typing"],
  ["INTEGRASI", "INTEGRATIONS"],
  ["Perangkat IoT", "IoT devices"],
  ["Cari perangkat", "Search devices"],
  ["Cari perangkat IoT", "Search IoT devices"],
  ["Filter jenis perangkat", "Filter device type"],
  ["Semua", "All"],
  ["Kamera", "Camera"],
  ["Sensor", "Sensor"],
  ["Daftar perangkat", "Device list"],
  ["Online", "Online"],
  ["Perangkat tidak ditemukan.", "No devices found."],
  ["Cuplikan terbaru · simulasi", "Latest snapshot · demo"],
  ["Status dan data perangkat adalah simulasi.", "Device status and readings are simulated."],
  ["Gudang utama", "Main warehouse"],
  ["Area staf", "Staff area"],
  ["Kamera Gudang", "Warehouse camera"],
  ["Kamera Area Staf", "Staff area camera"],
  ["Sensor Suhu", "Temperature sensor"],
  ["Online · demo", "Online · demo"],
  ["3 dus terlihat", "3 boxes detected"],
  ["Objek terdeteksi · simulasi", "Objects detected · demo"],
  ["Stabil", "Stable"],
  ["Baru saja", "Just now"],
  ["2 menit lalu", "2 minutes ago"],
  ["Area terlihat normal", "Area looks clear"],
  ["Ringkasan gambar · simulasi", "Image summary · demo"],
  ["Normal", "Normal"],
  ["Suhu ruangan · simulasi", "Room temperature · demo"],
  ["Pilih topik chat", "Choose a conversation"],
  ["Rencana tugas", "Task plan"],
  ["Rencana untuk instruksi ini.", "Plan for this instruction."],
  ["Pesan", "Message"],
  ["Sumber", "Source"],
  ["suhu", "temperature"],
  ["jumlah pesanan yang belum dikemas", "number of unpacked orders"],
  ["jumlah pesanan yang berbeda", "number of mismatched orders"],
  ["sama dengan", "equals"],
  ["tidak sama dengan", "does not equal"],
  ["lebih dari", "greater than"],
  ["setidaknya", "at least"],
  ["kurang dari", "less than"],
  ["paling banyak", "at most"],
  ["berdasarkan langkah", "based on step"],
  ["Dijalankan sekali", "Runs once"],
  ["Setiap {interval} detik · maksimal {runs} pemeriksaan", "Every {interval} seconds · up to {runs} checks"],
  ["Ada kendala", "Something went wrong"],
  ["Hasil pemeriksaan", "Check result"],
  ["selesai", "completed"],
  ["Lihat hasil", "View result"],
  ["Setujui & mulai", "Approve & start"],
  ["Jeda", "Pause"],
  ["Lanjutkan", "Resume"],
  ["Jalankan ulang", "Run again"],
  ["Batalkan", "Cancel"],
  ["PEMANTAUAN", "MONITORING"],
  ["Pantau pekerjaan yang dibuat dari percakapanmu.", "Monitor tasks created from your conversations."],
  ["＋ Tugas baru", "＋ New task"],
  ["tugas aktif", "active tasks"],
  ["Terjadwal", "Scheduled"],
  ["Detail", "Details"],
  ["Detail tugas", "Task details"],
  ["Ringkasan", "Summary"],
  ["Jadwal", "Schedule"],
  ["Progres", "Progress"],
  ["Kondisi", "Condition"],
  ["detik", "seconds"],
  ["Tutup", "Close"],
  ["menunggu persetujuan", "awaiting approval"],
  ["Belum ada tugas", "No tasks yet"],
  ["Ceritakan apa yang ingin dipantau. Rencana akan muncul di sini.", "Tell Kanca what you want to monitor. Plans will appear here."],
  ["Mulai percakapan", "Start a conversation"],
  ["Sekali", "Once"],
  ["Setiap {interval} detik", "Every {interval} seconds"],
  ["{done} / {max} pemeriksaan", "{done} / {max} checks"],
  ["Dibuat", "Created"],
  ["Jeda pemeriksaan (detik)", "Check interval (seconds)"],
  ["Maksimal pemeriksaan", "Maximum number of checks"],
  ["Perubahan membutuhkan persetujuan kembali sebelum tugas dilanjutkan.", "Changes need approval before the task can resume."],
  ["Simpan perubahan", "Save changes"],
  ["Batal", "Cancel"],
  ["Hentikan", "Stop"],
  ["Ubah jadwal", "Edit schedule"],
  ["Hapus dari daftar", "Remove from list"],
  ["AKTIVITAS", "ACTIVITY"],
  ["Pembaruan terbaru dari tugas latar belakangmu.", "Recent updates from your background tasks."],
  ["Tandai semua dibaca", "Mark all as read"],
  ["Belum ada notifikasi", "No notifications yet"],
  ["Pembaruan tugas akan muncul di sini.", "Task updates will appear here."],
  ["Belum dibaca", "Unread"],
  ["Tandai dibaca", "Mark as read"],
  ["Tugas menunggu persetujuan", "Task needs approval"],
  ["Tugas selesai", "Task completed"],
  ["Tugas gagal", "Task failed"],
  ["Ada hal yang perlu perhatianmu", "Needs your attention"],
  ["Tugas dihentikan", "Task stopped"],
  ["Tugas dijeda", "Task paused"],
  ["Tugas dilanjutkan", "Task resumed"],
  ["Hapus tugas dari daftar?", "Remove task from the list?"],
  ["Tugas yang aktif akan dihentikan. Riwayatnya tetap disimpan.", "Active tasks will stop. Their history will be kept."],
  ["Hapus percakapan?", "Delete conversation?"],
  ["Percakapan akan dihapus dari daftar. Tugas yang sudah dibuat tetap berjalan dan tersedia di Tugas latar belakang.", "This conversation will be removed. Its tasks will keep running and remain available under Background tasks."],
  ["Opsi untuk {title}", "Options for {title}"],
  ["Hasil analisis gambar", "Image analysis result"],
  ["Hasil analisis audio", "Audio analysis result"],
  ["Ringkasan", "Summary"],
  ["Perkiraan jumlah", "Estimated count"],
  ["Kepastian", "Confidence"],
  ["Catatan", "Note"],
  ["Alasan", "Reason"],
  ["Tindakan", "Action"],
  ["Belum pasti", "Uncertain"],
  ["Cukup yakin", "Likely"],
  ["Jenis hasil", "Result type"],
  ["Waktu pemeriksaan", "Check time"],
  ["Hasil ini belum pasti; AI tidak dapat memastikan jawabannya.", "This result is uncertain; the AI cannot confirm it."],
  ["Ringkasan analisis tidak tersedia.", "Analysis summary unavailable."],
  ["Perkiraan jumlah:", "Estimated count:"],
  ["Tutup detail sumber", "Close source details"],
  ["Aktif", "Active"],
  ["Nonaktif", "Inactive"],
  ["Data terakhir", "Last data received"],
  ["Belum menerima data", "No data received yet"],
  ["Riwayat diperbarui otomatis tiap 5 detik", "History refreshes every 5 seconds"],
  ["Data terbaru", "Latest data"],
  ["Memuat data aplikasi…", "Loading app data…"],
  ["Memperbarui…", "Refreshing…"],
  ["Memuat data…", "Loading data…"],
  ["Mengambil data satu kali…", "Getting data once…"],
  ["Mengambil data…", "Fetching data…"],
  ["Periksa data sekarang", "Check for data now"],
  ["Get Data lagi", "Get Data again"],
  ["Data baru diterima.", "New data received."],
  ["Gambar baru diterima; analisis AI mungkin masih diproses.", "New image received; AI analysis may still be processing."],
  ["Riwayat dimuat manual.", "History is refreshed manually."],
  ["Belum menerima data baru. Periksa gateway dan feed, lalu coba Get Data lagi.", "No new data received. Check the gateway and feed, then try Get Data again."],
  ["Permintaan data gagal.", "The data request failed."],
  ["Frame berhasil diambil, tetapi analisis AI gagal. Cuplikannya tetap bisa dilihat; klik Get Data lagi untuk mencoba ulang.", "The frame was captured, but AI analysis failed. You can still view it; click Get Data again to retry."],
  ["Cuplikan kamera", "Camera snapshot"],
  ["Mengambil gambar dari kamera…", "Fetching camera image…"],
  ["Menunggu kamera mengirim gambar. Proses ini bisa memerlukan beberapa saat.", "Waiting for the camera to send an image. This may take a moment."],
  ["Memperbarui cuplikan…", "Refreshing snapshot…"],
  ["Gambar belum diterima. Periksa gateway atau feed, lalu coba lagi.", "No image received. Check the gateway or feed, then try again."],
  ["Pengambilan terbaru belum berhasil; cuplikan sebelumnya ditampilkan.", "The latest capture did not complete; showing the previous snapshot."],
  ["Cuplikan diterima, menunggu analisis…", "Snapshot received; waiting for analysis…"],
  ["Analisis AI gagal; cuplikan tetap tersedia.", "AI analysis failed; the snapshot is still available."],
  ["Belum ada data yang diterima dari sumber ini.", "This source has not sent any data yet."],
  ["Permintaan data satu kali dikirim ke gateway. Feed publik tidak dibaca berkala.", "A one-time data request was sent to the gateway. Public feeds are not polled on a schedule."],
  ["Aktifkan sumber sebelum meminta data.", "Enable the source before requesting data."],
  ["Aktifkan Analisis gambar di Atur media sebelum meminta cuplikan kamera.", "Enable image analysis in Media settings before requesting a camera snapshot."],
  ["Jenis sumber ini tidak mendukung permintaan data satu kali.", "This source type does not support one-time data requests."],
  ["Tutup", "Close"],
  ["Daftar sumber integrasi", "Integration source list"],
  ["Sumber perangkat", "Device sources"],
  ["Salin konfigurasi", "Copy configuration"],
  ["Konfigurasi tersalin.", "Configuration copied."],
  ["Konfigurasi tidak dapat disalin otomatis. Salin teks konfigurasi secara manual.", "The configuration could not be copied automatically. Copy it manually."],
  ["Webhook", "Webhook"],
  ["Kelola sumber data masuk dan webhook untuk event keluar.", "Manage incoming data sources and outgoing event webhooks."],
  ["Contoh: Sensor gudang", "Example: Warehouse sensor"],
  ["IoT / sensor", "IoT / sensor"],
  ["Layanan lain", "Other service"],
  ["Tambah sumber", "Add source"],
  ["Tambah sumber secara manual", "Add a source manually"],
  ["Ubah sumber", "Edit source"],
  ["Mengubah sumber", "Editing source"],
  ["Sumber dibuat", "Source created"],
  ["Salin token sekarang; token tidak akan ditampilkan lagi. Gunakan koneksi HTTPS saat mengirim data melalui jaringan.", "Copy the token now; it will not be shown again. Use HTTPS when sending data over a network."],
  ["Alamat penerima", "Ingest URL"],
  ["Alamat localhost hanya dapat diakses dari mesin ini. Perangkat lain memerlukan gateway yang aman.", "A localhost address is only reachable from this machine. Other devices need a secure gateway."],
  ["Saya sudah menyimpan token", "I have saved the token"],
  ["Sumber terhubung", "Connected sources"],
  ["sumber terdaftar", "registered sources"],
  ["Cari nama sumber", "Search source name"],
  ["Cari sumber integrasi", "Search integrations"],
  ["Filter jenis sumber", "Filter source type"],
  ["Status", "Status"],
  ["Layanan", "Service"],
  ["Data terakhir diterima", "Last data received"],
  ["Belum ada sumber", "No sources yet"],
  ["Tambahkan kamera, sensor, atau layanan untuk mulai menerima data.", "Add a camera, sensor, or service to start receiving data."],
  ["Sumber tidak ditemukan", "No sources found"],
  ["Coba ubah kata pencarian atau filter yang dipilih.", "Try changing your search or filters."],
  ["Lihat data", "View data"],
  ["Get Data", "Get Data"],
  ["Live Streaming", "Live Streaming"],
  ["Pembaruan otomatis tiap 5 detik", "Auto refresh every 5 seconds"],
  ["Preview kamera simulasi", "Simulated camera preview"],
  ["Gambar demo; data perangkat diperbarui berkala.", "Demo image; device data refreshes periodically."],
  ["Streaming video langsung belum tersedia untuk sumber ini. Event terbaru tetap diperbarui berkala.", "Live video is not available for this source. Latest events still refresh periodically."],
  ["Sumber mengirim cuplikan berkala, bukan video langsung.", "This source sends periodic snapshots, not live video."],
  ["Perbarui sekarang", "Refresh now"],
  ["CCTV Publik Gatot Subroto", "Public CCTV Gatot Subroto"],
  ["CCTV Publik Gerbang Pemuda", "Public CCTV Gerbang Pemuda"],
  ["Untuk mengganti kamera publik, hapus dulu sumber yang bernama sama.", "To replace public cameras, delete the sources with the same names first."],
  ["Cuaca Kemayoran (BMKG)", "Kemayoran Weather (BMKG)"],
  ["Prakiraan cuaca, suhu, kelembapan, dan angin · diperbarui BMKG 2 kali sehari.", "Weather forecast, temperature, humidity, and wind · BMKG updates twice daily."],
  ["Gempa Terbaru (BMKG)", "Latest Earthquake (BMKG)"],
  ["Parameter kejadian gempa terbaru di Indonesia.", "Latest earthquake details for Indonesia."],
  ["Gempa Dirasakan (BMKG)", "Felt Earthquakes (BMKG)"],
  ["Daftar hingga 15 kejadian gempa yang dirasakan.", "Up to 15 recent felt earthquake reports."],
  ["Hubungkan sumber BMKG", "Connect BMKG sources"],
  ["Menyambungkan…", "Connecting…"],
  ["Semua sumber BMKG sudah terhubung.", "All BMKG sources are connected."],
  ["Atribusi wajib: BMKG (Badan Meteorologi, Klimatologi, dan Geofisika). Cuaca diprakirakan, bukan pembacaan sensor langsung.", "Required attribution: BMKG (Indonesia's Meteorology, Climatology, and Geophysics Agency). Weather values are forecasts, not direct sensor readings."],
  ["Konfigurasi gateway BMKG", "BMKG gateway configuration"],
  ["Tambahkan objek ini ke array sources pada config.json gateway yang sudah ada. Jangan hapus sumber yang lain. Token hanya tampil sekarang.", "Add these entries to the sources array in your existing gateway config.json. Keep the other sources. Tokens are shown only now."],
  ["Simpan konfigurasi BMKG", "Copy BMKG configuration"],
  ["Sumber publik siap dihubungkan", "Public sources ready to connect"],
  ["Sumber BMKG terdaftar", "BMKG sources are registered"],
  ["Suhu, kelembapan, dan cuaca", "Temperature, humidity, and weather"],
  ["Gempa terbaru dan laporan gempa dirasakan", "Latest earthquake and felt reports"],
  ["Setiap 2 menit", "Every 2 minutes"],
  ["Setiap 1 jam", "Every hour"],
  ["Menunggu data pertama dari gateway.", "Waiting for the first data from the gateway."],
  ["CCTV publik DKI Jakarta · tayangan langsung", "DKI Jakarta public CCTV · live feed"],
  ["Kamera publik mengirim cuplikan untuk analisis AI berkala; player langsung mengikuti portal sumber.", "Public cameras send periodic snapshots for AI analysis; the live player comes from the source portal."],
  ["Atur media", "Media settings"],
  ["Ubah", "Edit"],
  ["Nonaktifkan", "Disable"],
  ["Aktifkan", "Enable"],
  ["Pertanyaan tentang gambar", "Image analysis prompt"],
  ["Pertanyaan tentang audio", "Audio analysis prompt"],
  ["Analisis gambar", "Image analysis"],
  ["Analisis audio", "Audio analysis"],
  ["Media yang diaktifkan akan dikirim ke Baseten untuk dianalisis. Aktifkan hanya sesuai kebutuhan.", "Enabled media will be sent to Baseten for analysis. Enable only what you need."],
  ["Jenis integrasi", "Integration type"],
  ["KELUAR", "OUTBOUND"],
  ["Kirim event Kanca ke endpoint HTTPS milikmu. Secret hanya ditampilkan saat webhook dibuat.", "Send Kanca events to your HTTPS endpoint. The signing secret is only shown when the webhook is created."],
  ["URL endpoint", "Endpoint URL"],
  ["Tambah webhook", "Add webhook"],
  ["Endpoint harus menggunakan HTTPS, port 443, dan alamat IP publik.", "Endpoints must use HTTPS, port 443, and a public IP address."],
  ["Webhook berhasil dibuat", "Webhook created"],
  ["Simpan secret ini sekarang. Kanca tidak dapat menampilkannya lagi setelah bagian ini ditutup.", "Save this secret now. Kanca cannot show it again after you close this panel."],
  ["Signing secret", "Signing secret"],
  ["Salin secret", "Copy secret"],
  ["Secret disalin.", "Secret copied."],
  ["Salin secret secara manual.", "Copy the secret manually."],
  ["Saya sudah menyimpan", "I have saved it"],
  ["Endpoint terdaftar", "Registered endpoints"],
  ["aktif", "active"],
  ["total", "total"],
  ["Muat ulang", "Refresh"],
  ["Belum ada webhook. Tambahkan URL endpoint di atas untuk menerima event.", "No webhooks yet. Add an endpoint URL above to receive events."],
  ["Riwayat pengiriman", "Delivery history"],
  ["Maksimal 100 pengiriman terbaru", "Up to 100 recent deliveries"],
  ["Menunggu", "Pending"],
  ["Mengirim", "Sending"],
  ["Terkirim", "Delivered"],
  ["Gagal", "Failed"],
  ["Tidak ada pengiriman dengan status ini.", "No deliveries with this status."],
  ["Belum ada event untuk dikirim.", "No events to deliver yet."],
  ["Filter status pengiriman", "Filter delivery status"],
  ["percobaan", "attempts"],
  ["belum ada respons HTTP", "no HTTP response yet"],
  ["Endpoint webhook", "Webhook endpoint"],
  ["Nonaktifkan webhook?", "Disable webhook?"],
  ["Kanca tidak akan mengirim event baru ke {url}. Riwayat pengiriman tetap tersimpan.", "Kanca will stop sending new events to {url}. Delivery history will be kept."],
  ["Nama sumber", "Source name"],
  ["Jenis", "Type"],
  ["Sumber menerima", "Sources accept"],
  ["Sumber:", "Source:"],
  ["Jika", "If"],
  ["Pemeriksaan", "checks"],
  ["Suhu ruangan", "Room temperature"],
  ["Cek kondisi suhu", "Check the temperature"],
  ["Cek pesanan", "Check orders"],
  ["Tidak ada sumber yang ditemukan.", "No sources found."],
  ["Respons server tidak dapat dibaca.", "The server response could not be read."],
  ["Permintaan gagal", "Request failed"],
  ["Belum ada data", "No data yet"],
  ["Belum ada percakapan", "No conversations yet"],
  ["Filter status sumber", "Filter source status"],
  ["Hapus sumber?", "Delete source?"],
  ["Kirim instruksi", "Send instruction"],
  ["Memuat endpoint…", "Loading endpoints…"],
  ["Riwayat data sumber", "Source data history"],
  ["Token", "Token"],
  ["belum dibaca", "unread"],
  ["perangkat", "devices"],
  ["{name} tidak dapat mengirim data lagi. Riwayatnya tetap tersimpan.", "{name} can no longer send data. Its history will be kept."],
  ["Beralih ke bahasa Inggris", "Switch to English"],
  ["Beralih ke bahasa Indonesia", "Switch to Indonesian"],
  ["Instruksi cepat", "Quick prompts"],
  ["Tutup", "Close"],
  ["Rencana baru sudah dibuat. Periksa dan setujui untuk menjalankannya.", "A new plan is ready. Review and approve it to run."],
  ["Perangkat", "Devices"],
  ["Dibuat untuk", "Created for"],
  ["Menunggu persetujuan", "Awaiting approval"],
  ["Dipantau", "Scheduled"],
  ["Dijeda", "Paused"],
  ["Sedang berjalan", "Running"],
  ["Selesai", "Completed"],
  ["Dibatalkan", "Cancelled"],
  ["Membaca pesanan simulasi", "Read simulated orders"],
  ["Memeriksa pesanan dan selisih", "Check orders and discrepancies"],
  ["Membuat pengingat simulasi", "Create a simulated reminder"],
  ["Membaca suhu simulasi", "Read simulated temperature"],
  ["Menyalakan lampu simulasi", "Turn on simulated light"],
  ["Membaca data terbaru dari sumber eksternal", "Read the latest external data"],
  ["Membuat pemberitahuan untuk pemilik", "Notify the owner"],
  ["Tren sensor", "Sensor trends"],
  ["Tidak ada sumber publik", "No public sources"],
  ["Sumber publik belum tersedia.", "Public sources are not available."],
  ["Sumber publik", "Public sources"],
  ["Jelajahi sumber publik", "Browse public sources"],
  ["Lihat semua sumber publik", "View all public sources"],
  ["Cari nama, penyedia, atau field", "Search name, provider, or field"],
  ["Cari sumber publik", "Search public sources"],
  ["Semua jenis", "All types"],
  ["Kamera", "Camera"],
  ["Negara", "Country"],
  ["Semua negara", "All countries"],
  ["Ketersediaan", "Availability"],
  ["Belum terhubung", "Not connected"],
  ["Sebagian terhubung", "Partially connected"],
  ["Terhubung", "Connected"],
  ["Tersedia", "Available"],
  ["Feed", "Feeds"],
  ["Penyedia", "Provider"],
  ["Field", "Fields"],
  ["cuaca", "weather"],
  ["suhu", "temperature"],
  ["kelembapan", "humidity"],
  ["angin", "wind"],
  ["magnitudo gempa", "earthquake magnitude"],
  ["lokasi", "location"],
  ["laporan gempa dirasakan", "felt earthquake reports"],
  ["lalu lintas", "traffic"],
  ["kondisi jalan", "road conditions"],
  ["cuplikan kamera", "camera snapshots"],
  ["Feed data publik BMKG", "BMKG public data feeds"],
  ["Prakiraan cuaca dan laporan gempa dari feed resmi BMKG.", "Weather forecasts and earthquake reports from official BMKG feeds."],
  ["Cuaca Kemayoran", "Kemayoran weather"],
  ["Gempa terbaru", "Latest earthquake"],
  ["Gempa dirasakan", "Felt earthquakes"],
  ["CCTV publik DKI Jakarta", "DKI Jakarta public CCTV"],
  ["Dua feed kamera lalu lintas publik dengan analisis gambar berkala.", "Two public traffic camera feeds with periodic image analysis."],
  ["Gatot Subroto", "Gatot Subroto"],
  ["Gerbang Pemuda", "Gerbang Pemuda"],
  ["Global", "Global"],
  ["Sumber terdaftar", "Registered sources"],
  ["Data terbaru", "Recent data"],
  ["Perlu perhatian", "Needs attention"],
  ["Kamera, IoT, dan layanan", "Cameras, IoT, and services"],
  ["feed tersedia", "feeds available"],
  ["Memuat lokasi BMKG…", "Loading BMKG locations…"],
  ["Tampilkan 24 lokasi berikutnya", "Show the next 24 locations"],
  ["Sumber publik dibuat nonaktif. Aktifkan dari kartunya sebelum menjalankan gateway.", "Public sources are created disabled. Enable them on their cards before starting the gateway."],
  ["Event keluar", "Outgoing events"],
  ["Prakiraan cuaca global", "Global weather forecasts"],
  ["Data prakiraan cuaca tanpa kunci API untuk beberapa kota.", "Weather forecasts for several cities, with no API key required."],
  ["Cuaca Jakarta (Open-Meteo)", "Jakarta Weather (Open-Meteo)"],
  ["Cuaca Singapura (Open-Meteo)", "Singapore Weather (Open-Meteo)"],
  ["Cuaca Tokyo (Open-Meteo)", "Tokyo Weather (Open-Meteo)"],
  ["Prakiraan cuaca", "Weather forecast"],
  ["Singapura", "Singapore"],
  ["Curah hujan", "Precipitation"],
  ["Kecepatan angin", "Wind speed"],
  ["Aktivitas gempa global", "Global earthquake activity"],
  ["Feed gempa signifikan dan aktivitas gempa terbaru di seluruh dunia.", "Significant and recent earthquake feeds from around the world."],
  ["Gempa Signifikan Global (USGS)", "Global Significant Earthquakes (USGS)"],
  ["Gempa 24 Jam Global (USGS)", "Global Earthquakes in 24 Hours (USGS)"],
  ["Gempa signifikan 30 hari", "Significant earthquakes in 30 days"],
  ["Gempa 24 jam", "Earthquakes in 24 hours"],
  ["Kedalaman", "Depth"],
  ["Waktu gempa", "Earthquake time"],
  ["Hubungkan Open-Meteo", "Connect Open-Meteo"],
  ["Hubungkan USGS", "Connect USGS"],
  ["Sumber publik tidak ditemukan", "No public sources found"],
  ["Coba ubah pencarian atau filter.", "Try changing the search or filters."],
  ["Sebagian feed sudah ada. Hapus sumber CCTV yang ada sebelum membuat paket lagi.", "Some feeds already exist. Remove existing CCTV sources before creating the pack again."],
  ["Sumber publik siap", "Public sources are ready"],
  ["Simpan token gateway sekarang. Token hanya ditampilkan sekali.", "Save the gateway tokens now. Tokens are shown only once."],
  ["Konfigurasi gateway", "Gateway configuration"],
  ["Salin konfigurasi", "Copy configuration"],
  ["Hubungkan sumber tersisa", "Connect remaining sources"],
  ["Hubungkan BMKG", "Connect BMKG"],
  ["Hubungkan BaliTower / Jakarta", "Connect BaliTower / Jakarta"],
  ["Tren muncul setelah ada sedikitnya dua observasi numerik dengan field yang sama.", "A trend appears after two numeric observations with the same field."],
  ["Angka berasal dari payload sumber; observasi media yang tidak pasti tidak disertakan.", "Values come from source payloads; uncertain media observations are excluded."],
  ["Ekspor CSV", "Export CSV"],
  ["Ekspor JSON", "Export JSON"],
  ["Ekspor batch event CSV", "Export an event batch as CSV"],
  ["Ekspor batch event JSON", "Export an event batch as JSON"],
  ["Status penerimaan memakai waktu event terakhir dan interval harapan; proses gateway tidak diperiksa langsung.", "Receiving status uses the last event time and expected interval; gateway process health is not checked directly."],
  ["observasi", "observations"],
  ["Target kirim", "Expected interval"],
  ["Interval data harapan (detik)", "Expected data interval (seconds)"],
  ["Data terbaru", "Recent data"],
  ["Menunggu data", "Waiting for data"],
  ["Terlambat", "Delayed"],
  ["Observasi ini sudah melewati batas kesegaran sumber.", "This observation is beyond the source freshness window."],
  ["Status tidak diketahui", "Unknown status"],
  ["Atur jenis notifikasi", "Notification preferences"],
  ["Simpan preferensi", "Save preferences"],
  ["Pilih event webhook", "Choose webhook events"],
  ["Atur event", "Configure events"],
  ["Jenis event", "Event types"],
  ["Ekspor tidak dapat diunduh.", "Export could not be downloaded."],
  ["jam", "hours"],
  ["menit", "minutes"],
  ["detik", "seconds"],
]);
function useLanguage() { return useContext(LanguageContext); }

function formatRelativeTime(value, locale) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const elapsed = date.getTime() - Date.now();
  const absolute = Math.abs(elapsed);
  const relative = new Intl.RelativeTimeFormat(locale, {numeric:'auto'});
  if (absolute < 45_000) return relative.format(0, 'second');
  const units = [
    ['minute', 60_000],
    ['hour', 3_600_000],
    ['day', 86_400_000],
    ['week', 604_800_000],
    ['month', 2_629_746_000],
    ['year', 31_556_952_000],
  ];
  const [unit, duration] = units.find(([, size]) => absolute < size * 1.5) || units[units.length - 1];
  return relative.format(Math.round(elapsed / duration), unit);
}

const labels = {awaiting_approval:'Menunggu persetujuan', scheduled:'Terjadwal', paused:'Dijeda', running:'Sedang berjalan', completed:'Selesai', failed:'Gagal', cancelled:'Dibatalkan'};
const capabilities = {'business.list_orders':'Membaca pesanan simulasi','business.check_orders':'Memeriksa pesanan dan selisih','business.remind':'Membuat pengingat simulasi','device.read_temperature':'Membaca suhu simulasi','device.turn_on_light':'Menyalakan lampu simulasi','external.latest_event':'Membaca data terbaru dari sumber eksternal','external.escalate':'Membuat pemberitahuan untuk pemilik'};
const fields = {temperature_c:'suhu', unpacked_count:'jumlah pesanan yang belum dikemas', mismatch_count:'jumlah pesanan yang berbeda'};
const operators = {eq:'sama dengan', ne:'tidak sama dengan', gt:'lebih dari', gte:'setidaknya', lt:'kurang dari', lte:'paling banyak'};

const iconPaths = {
  plus: <path d="M12 5v14M5 12h14"/>,
  trash: <><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v5M14 11v5"/></>,
  dashboard: <><rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" height="5" rx="1.5"/><rect x="13" y="10" width="8" height="11" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/></>,
  chat: <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22l5.9-2Z"/>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/></>,
  check: <path d="m5 12 4 4L19 6"/>,
  plug: <path d="M12 22v-5M9 8V2M15 8V2M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></>,
  dots: <path strokeWidth="2.6" d="M12 6h.01M12 12h.01M12 18h.01"/>,
  search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
  camera: <><path d="M14 5 12.5 3h-5L6 5H3a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h18a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-7Z"/><circle cx="12" cy="12" r="3"/></>,
  up: <path d="M12 19V5M5 12l7-7 7 7"/>,
  thermometer: <path d="M14 4v10.5a4 4 0 1 1-4 0V4a2 2 0 1 1 4 0Z"/>,
  list: <path d="M8.5 6H20M8.5 12H20M8.5 18H20M4 6h.01M4 12h.01M4 18h.01"/>,
  sun: <><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M5 5l1.8 1.8M17.2 17.2 19 19M19 5l-1.8 1.8M6.8 17.2 5 19"/></>,
  moon: <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z"/>,
  close: <path d="m18 6-12 12M6 6l12 12"/>,
  chevron: <path d="m7 10 5 5 5-5"/>
};
function Icon({name, size=20}) {
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{iconPaths[name]}</svg>;
}

function Brand({className='brand'}) {
  return <div className={className}><div className="brand-icon">k.</div><span className="brand-name">kanca</span></div>;
}

const demoIoTDevices = [
  {id:'warehouse-camera',name:'Kamera Gudang',type:'Kamera',location:'Gudang utama',status:'Online · demo',image:warehouseDemo,snapshot:'Baru saja',reading:'3 dus terlihat',readingLabel:'Objek terdeteksi · simulasi',state:'Stabil'},
  {id:'staff-camera',name:'Kamera Area Staf',type:'Kamera',location:'Area staf',status:'Online · demo',image:staffCameraDemo,snapshot:'2 menit lalu',reading:'Area terlihat normal',readingLabel:'Ringkasan gambar · simulasi',state:'Normal'},
  {id:'warehouse-temperature',name:'Sensor Suhu',type:'Sensor',location:'Gudang utama',status:'Online · demo',reading:'24°C',readingLabel:'Suhu ruangan · simulasi',state:'Normal'}
];

function IoTPanel() {
  const {language,t}=useLanguage();
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('Semua');
  const [selectedId, setSelectedId] = useState(demoIoTDevices[0].id);
  const categories = ['Semua', 'Kamera', 'Sensor'];
  const filteredDevices = demoIoTDevices.filter(device => (category === 'Semua' || device.type === category) && `${device.name} ${device.location}`.toLowerCase().includes(query.trim().toLowerCase()));
  const selectedDevice = filteredDevices.find(device => device.id === selectedId) || filteredDevices[0];

  return <aside className="iot-panel" aria-label={t('Perangkat IoT')}>
    <div className="iot-panel-heading"><div><div className="eyebrow">{t('INTEGRASI')}</div><h2>{t('Perangkat IoT')}</h2></div><span className="iot-count" aria-label={`${demoIoTDevices.length} ${t('perangkat')}`}>{demoIoTDevices.length}</span></div>
    <label className="iot-search"><Icon name="search" size={16}/><input type="search" value={query} onChange={event=>setQuery(event.target.value)} placeholder={t('Cari perangkat')} aria-label={t('Cari perangkat IoT')}/></label>
    <div className="iot-filters" role="group" aria-label={t('Filter jenis perangkat')}>{categories.map(item=><button key={item} className={category===item?'active':''} aria-pressed={category===item} onClick={()=>setCategory(item)}>{t(item)}</button>)}</div>
    <div className="iot-device-list" aria-label={t('Daftar perangkat')}>{filteredDevices.length ? filteredDevices.map(device=><button key={device.id} className={`iot-device-option ${selectedDevice?.id===device.id?'selected':''}`} aria-pressed={selectedDevice?.id===device.id} onClick={()=>setSelectedId(device.id)}><span className="iot-device-mark"><Icon name={device.type==='Kamera'?'camera':'thermometer'} size={17}/></span><span className="iot-device-option-copy"><strong>{t(device.name)}</strong><span>{t(device.type)} · {t(device.location)}</span></span><span className="iot-device-state"><i/>{t('Online')}</span></button>) : <p className="iot-empty">{t('Perangkat tidak ditemukan.')}</p>}</div>
    {selectedDevice && <article className="iot-card iot-detail-card">
      <div className="iot-device-heading"><div><strong>{t(selectedDevice.name)}</strong><span className="iot-device-type">{t(selectedDevice.location)}</span></div><span className="iot-status"><i/>{t(selectedDevice.status)}</span></div>
      {selectedDevice.image && <figure className="iot-snapshot"><img src={selectedDevice.image} alt={`${t('Cuplikan terbaru · simulasi')} ${t(selectedDevice.name).toLowerCase()}`}/><figcaption><span>{t('Cuplikan terbaru · simulasi')}</span><span>{t(selectedDevice.snapshot)}</span></figcaption></figure>}
      <div className="iot-reading"><span className="iot-reading-icon" aria-hidden="true">{selectedDevice.type==='Kamera'?'▦':'°'}</span><div><strong>{t(selectedDevice.reading)}</strong><span>{t(selectedDevice.readingLabel)}</span></div><span className="iot-reading-state">{t(selectedDevice.state)}</span></div>
      <p className="iot-demo-note">{t('Status dan data perangkat adalah simulasi.')}</p>
    </article>}
  </aside>;
}

function ChatTopics({chats, current, onSelect, onNew}) {
  const {t}=useLanguage();
  const [open,setOpen]=useState(false);
  const picker=useRef(null);
  const activeTitle=chats.find(chat=>chat.id===current)?.title || t('Pilih topik chat');
  useEffect(()=>{
    if(!open)return;
    const selectedOption=picker.current?.querySelector('[role="option"][aria-selected="true"]');
    (selectedOption || picker.current?.querySelector('[role="option"]'))?.focus();
    const onPointerDown=event=>{if(!picker.current?.contains(event.target))setOpen(false);};
    const onKeyDown=event=>{if(event.key==='Escape'){setOpen(false);picker.current?.querySelector('.topic-picker-trigger')?.focus();}};
    document.addEventListener('pointerdown',onPointerDown);
    document.addEventListener('keydown',onKeyDown);
    return()=>{document.removeEventListener('pointerdown',onPointerDown);document.removeEventListener('keydown',onKeyDown);};
  },[open]);
  function chooseChat(id){setOpen(false);onSelect(id);}
  function moveOption(event){
    const options=[...picker.current.querySelectorAll('[role="option"]')];
    const index=options.indexOf(document.activeElement);
    const next=event.key==='ArrowDown'?(index+1)%options.length:(index-1+options.length)%options.length;
    event.preventDefault();options[next]?.focus();
  }
  return <div className="topic-picker" ref={picker}>
    <button type="button" className="topic-picker-trigger" aria-label={t('Pilih topik chat')} aria-expanded={open} aria-controls="chat-topic-options" onClick={()=>setOpen(value=>!value)} onKeyDown={event=>{if(event.key==='ArrowDown'&&!open){event.preventDefault();setOpen(true);}}}>
      <span className="topic-picker-copy"><span className="topic-picker-caption">{t('Percakapan')}</span><strong title={activeTitle}>{activeTitle}</strong></span><Icon name="chevron" size={18}/>
    </button>
    {open && <div className="topic-picker-menu" id="chat-topic-options" role="listbox" aria-label={t('Pilih topik chat')} onKeyDown={event=>{if(event.key==='ArrowDown'||event.key==='ArrowUp')moveOption(event);}}>
      <button type="button" role="option" aria-selected="false" className="topic-picker-new" onClick={()=>{setOpen(false);onNew();}}><Icon name="plus" size={17}/><span>{t('Chat baru')}</span></button>
      {['active','draft'].map(status=>{const group=chats.filter(chat=>chat.status===status);return group.length>0 && <div className="topic-picker-group" key={status}><p>{t(status==='draft'?'Draft':'Percakapan')}</p>{group.map(chat=><button type="button" role="option" aria-selected={chat.id===current} className={`topic-picker-option ${chat.id===current?'current':''}`} key={chat.id} title={chat.title} onClick={()=>chooseChat(chat.id)}>{chat.title}</button>)}</div>;})}
    </div>}
  </div>;
}

function useTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light');
  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    document.documentElement.dataset.theme = next;
    localStorage.setItem('kanca-theme', next);
    const meta = document.getElementById('theme-color');
    if (meta) meta.content = next === 'dark' ? '#0c1410' : '#f1f4ef';
  }
  return [theme, toggleTheme];
}

async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {'Content-Type': 'application/json', ...options.headers}});
  let data;
  try { data = await response.json(); } catch { throw new Error('Respons server tidak dapat dibaca.'); }
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === 'string' ? detail : detail?.clarification || JSON.stringify(detail || 'Permintaan gagal'));
  }
  return data;
}

function TaskCard({ task, onAction, onRerun }) {
  const {t}=useLanguage();
  const capabilityText = value => t(capabilities[value] || value);
  const format = (template, values) => Object.entries(values).reduce((text,[key,value])=>text.replace(`{${key}}`,value),t(template));
  return <div className="plan">
    <div className="plan-top"><strong>{t('Rencana tugas')}</strong><span className={`status ${task.status}`}>{t(labels[task.status] || task.status)}</span></div>
    <p>{task.plan.summary || t('Rencana untuk instruksi ini.')}</p>
    <ol>{(task.plan.steps || []).map((step, index) => <li key={index}>
      {capabilityText(step.capability)}
      {step.arguments?.message && <div className="details">{t('Pesan')}: {step.arguments.message}</div>}
      {step.arguments?.source_id && <div className="details">{t('Sumber')}: {step.arguments.source_id}</div>}
      {step.condition && <div className="details">{t('Jika')} {t(fields[step.condition.field] || step.condition.field)} {t(operators[step.condition.operator] || step.condition.operator)} {String(step.condition.value)} {t('berdasarkan langkah')} {step.condition.step + 1}.</div>}
    </li>)}</ol>
    {task.plan.schedule && <div className="meta">{task.plan.schedule.max_runs === 1 ? t('Dijalankan sekali') : format('Setiap {interval} detik · maksimal {runs} pemeriksaan',{interval:task.plan.schedule.interval_seconds,runs:task.plan.schedule.max_runs})}</div>}
    {task.result && <div className="result"><strong>{t(task.status === 'failed' ? 'Ada kendala' : 'Hasil pemeriksaan')}</strong>
      {task.result.error && <p>{task.result.error}</p>}
      {(task.result.steps || []).map((step, index) => <div key={index}><p>{capabilityText(step.capability)}: {t(step.status || 'selesai')}</p>
        {step.result && <details className="details"><summary>{t('Lihat hasil')}</summary><pre>{JSON.stringify(step.result, null, 2)}</pre></details>}</div>)}
      {(task.result.limitations || []).map((limit, index) => <p className="meta" key={index}>{limit}</p>)}
    </div>}
    <div className="actions">{task.status === 'awaiting_approval' && <button className="primary" onClick={() => onAction(task, 'approve', {version: task.version})}>{t('Setujui & mulai')}</button>}
      {task.status === 'scheduled' && <button className="secondary" onClick={() => onAction(task, 'pause')}>{t('Jeda')}</button>}
      {task.status === 'paused' && <button className="primary" onClick={() => onAction(task, 'resume')}>{t('Lanjutkan')}</button>}
      {!task.archived && ['completed','failed','cancelled'].includes(task.status) && <button className="secondary" onClick={() => onRerun(task)}>{t('Jalankan ulang')}</button>}
      {['awaiting_approval','scheduled','paused'].includes(task.status) && <button className="secondary" onClick={() => onAction(task, 'cancel')}>{t('Batalkan')}</button>}</div>
  </div>;
}

function Workers({ tasks, onAction, onEdit, onArchive, onCreate, onRerun }) {
  const {t,dateLocale}=useLanguage();
  const [editing, setEditing] = useState(null);
  const [selectedTask, setSelectedTask] = useState(null);
  const [interval, setInterval] = useState(60);
  const [runs, setRuns] = useState(1);
  const format = (template, values) => Object.entries(values).reduce((text,[key,value])=>text.replace(`{${key}}`,value),t(template));
  return <div className="workers"><div className="workers-header"><div><div className="eyebrow">{t('PEMANTAUAN')}</div><h1>{t('Tugas latar belakang')}</h1><p>{t('Pantau pekerjaan yang dibuat dari percakapanmu.')}</p></div><button className="primary" onClick={onCreate}>{t('＋ Tugas baru')}</button></div>
    <div className="worker-summary"><strong>{tasks.filter(t => t.status === 'scheduled' || t.status === 'running').length}</strong><span>{t('tugas aktif')}</span><span className="summary-divider"/><strong>{tasks.filter(t => t.status === 'awaiting_approval').length}</strong><span>{t('menunggu persetujuan')}</span></div>
    {!tasks.length && <div className="worker-empty"><strong>{t('Belum ada tugas')}</strong><p>{t('Ceritakan apa yang ingin dipantau. Rencana akan muncul di sini.')}</p><button className="secondary" onClick={onCreate}>{t('Mulai percakapan')}</button></div>}
    <div className="task-kanban">{[
      ['awaiting_approval', 'Menunggu persetujuan'],
      ['scheduled', 'Terjadwal'],
      ['running', 'Sedang berjalan'],
      ['paused', 'Dijeda'],
      ['completed', 'Selesai'],
      ['failed', 'Gagal'],
      ['cancelled', 'Dibatalkan'],
    ].map(([status, title]) => {
      const columnTasks = tasks.filter(task => task.status === status);
      return <section className={`task-kanban-column status-${status}`} key={status} aria-label={t(title)}>
        <header className="task-kanban-heading"><span className="task-kanban-marker"/><h2>{t(title)}</h2><span className="task-kanban-count">{columnTasks.length}</span></header>
        <div className="task-kanban-cards">{columnTasks.map(task => <article className="worker-card" key={task.id}>
      <div className="plan-top"><div className="task-card-title"><strong>{task.instruction}</strong><p>{task.plan.summary}</p></div></div>
      <div className="worker-meta"><span>{task.plan.schedule?.max_runs === 1 ? t('Sekali') : format('Setiap {interval} detik',{interval:task.plan.schedule?.interval_seconds})}</span><span>{format('{done} / {max} pemeriksaan',{done:task.result?.runs_completed || 0,max:task.plan.schedule?.max_runs || 1})}</span><span>{t('Dibuat')} {new Date(task.created_at).toLocaleString(dateLocale)}</span></div>
      {editing === task.id && <form className="schedule-form" onSubmit={async e => {e.preventDefault(); if(await onEdit(task, Number(interval), Number(runs))) setEditing(null);}}><label>{t('Jeda pemeriksaan (detik)')}<input type="number" min="1" max="86400" required value={interval} onChange={e=>setInterval(e.target.value)}/></label><label>{t('Maksimal pemeriksaan')}<input type="number" min="1" max="1000" required value={runs} onChange={e=>setRuns(e.target.value)}/></label><p>{t('Perubahan membutuhkan persetujuan kembali sebelum tugas dilanjutkan.')}</p><div className="actions"><button className="primary">{t('Simpan perubahan')}</button><button type="button" className="secondary" onClick={()=>setEditing(null)}>{t('Batal')}</button></div></form>}
      {task.status==='failed' && task.result?.error && <p className="worker-failure">{task.result.error}</p>}<div className="actions"><button className="secondary" onClick={()=>setSelectedTask(task)}>{t('Detail')}</button>{task.status === 'awaiting_approval' && <button className="primary" onClick={()=>onAction(task,'approve',{version:task.version})}>{t('Setujui & mulai')}</button>}{task.status === 'scheduled' && <button className="secondary" onClick={()=>onAction(task,'pause')}>{t('Jeda')}</button>}{task.status === 'paused' && <button className="primary" onClick={()=>onAction(task,'resume')}>{t('Lanjutkan')}</button>}{['awaiting_approval','scheduled','paused'].includes(task.status) && <><button className="secondary" onClick={()=>{setEditing(task.id);setInterval(task.plan.schedule?.interval_seconds || 1);setRuns(task.plan.schedule?.max_runs || 1);}}>{t('Ubah jadwal')}</button><button className="secondary" onClick={()=>onAction(task,'cancel')}>{t('Hentikan')}</button></>}{['completed','failed','cancelled'].includes(task.status) && <button className="secondary" onClick={()=>onRerun(task)}>{t('Jalankan ulang')}</button>}<button className="text-button" onClick={()=>onArchive(task)}>{t('Hapus dari daftar')}</button></div>
        </article>)}</div>
      </section>;
    })}</div>
    {selectedTask && <TaskDetailsDialog task={selectedTask} onClose={()=>setSelectedTask(null)}/>}
  </div>;
}

function TaskDetailsDialog({task,onClose}) {
  const {t,dateLocale}=useLanguage();
  const dialog=useRef(null);
  useEffect(()=>{dialog.current?.showModal();return()=>{if(dialog.current?.open)dialog.current.close();};},[]);
  return <dialog className="task-details-dialog" ref={dialog} onCancel={event=>{event.preventDefault();onClose();}} aria-labelledby="task-details-title">
    <div className="task-details-header"><div><div className="eyebrow">{t('Detail tugas')}</div><h2 id="task-details-title">{task.instruction}</h2></div><button className="icon-button" aria-label={t('Tutup')} onClick={onClose}><Icon name="close"/></button></div>
    <div className="task-details-content"><div className="task-details-status"><span className={`status ${task.status}`}>{t(labels[task.status]||task.status)}</span><span>{t('Dibuat')} {new Date(task.created_at).toLocaleString(dateLocale)}</span></div>
      {task.plan.summary && <section><h3>{t('Ringkasan')}</h3><p>{task.plan.summary}</p></section>}
      <section><h3>{t('Rencana tugas')}</h3><ol>{(task.plan.steps||[]).map((step,index)=><li key={index}><strong>{t(capabilities[step.capability]||step.capability)}</strong>{step.arguments&&Object.keys(step.arguments).length>0&&<pre>{JSON.stringify(step.arguments,null,2)}</pre>}{step.condition&&<p>{t('Kondisi')}: {step.condition.field} {step.condition.operator} {String(step.condition.value)}</p>}</li>)}</ol></section>
      {task.plan.schedule&&<section><h3>{t('Jadwal')}</h3><p>{task.plan.schedule.interval_seconds} {t('detik')} · {task.plan.schedule.max_runs} {t('pemeriksaan')}</p></section>}
      <section><h3>{t('Progres')}</h3><p>{task.result?.runs_completed||0} / {task.plan.schedule?.max_runs||1} {t('pemeriksaan')}</p>{task.result?.error&&<p className="worker-failure">{task.result.error}</p>}</section>
      {task.result&&<section><h3>{t('Hasil pemeriksaan')}</h3><pre>{JSON.stringify(task.result,null,2)}</pre></section>}
    </div>
    <div className="task-details-footer"><button className="secondary" onClick={onClose}>{t('Tutup')}</button></div>
  </dialog>;
}

const notificationLabels = {'task.approval_requested.v1':'Tugas menunggu persetujuan','task.completed.v1':'Tugas selesai','task.failed.v1':'Tugas gagal','task.escalated.v1':'Ada hal yang perlu perhatianmu','task.cancelled.v1':'Tugas dihentikan','task.paused.v1':'Tugas dijeda','task.resumed.v1':'Tugas dilanjutkan'};
function Notifications({ items, onRead, onReadAll, unreadCount, onRerun, onClose, onChanged }) {
  const {t,dateLocale}=useLanguage();
  const [preferences,setPreferences]=useState(null);
  const [preferenceError,setPreferenceError]=useState('');
  const [savingPreferences,setSavingPreferences]=useState(false);
  useEffect(()=>{api('/v1/notifications/preferences').then(setPreferences).catch(error=>setPreferenceError(error.message));},[]);
  function togglePreference(kind,checked){const next=preferences.event_types.filter(item=>item!==kind);if(checked)next.push(kind);setPreferences({...preferences,event_types:next});}
  async function savePreferences(){setSavingPreferences(true);try{const saved=await api('/v1/notifications/preferences',{method:'PUT',body:JSON.stringify({event_types:preferences.event_types})});setPreferences(saved);setPreferenceError('');await onChanged();}catch(error){setPreferenceError(error.message);}finally{setSavingPreferences(false);}}
  return <div className="workers"><div className="workers-header"><div><div className="eyebrow">{t('AKTIVITAS')}</div><h1>{t('Notifikasi')}</h1><p>{t('Pembaruan terbaru dari tugas latar belakangmu.')}</p></div><div className="notification-header-actions">{unreadCount>0 && <button className="secondary" onClick={onReadAll}>{t('Tandai semua dibaca')}</button>}{onClose && <button className="icon-button" aria-label={t('Tutup')} title={t('Tutup')} autoFocus onClick={onClose}><Icon name="close"/></button>}</div></div>
    <details className="notification-preferences"><summary>{t('Atur jenis notifikasi')}</summary>{preferences&&<><div className="preference-options">{preferences.available_types.map(kind=><label key={kind}><input type="checkbox" checked={preferences.event_types.includes(kind)} onChange={event=>togglePreference(kind,event.target.checked)}/>{t(notificationLabels[kind]||kind)}</label>)}</div><button className="secondary preference-save" type="button" disabled={savingPreferences} onClick={savePreferences}>{t(savingPreferences?'Menyimpan…':'Simpan preferensi')}</button></>}{preferenceError&&<p className="error">{preferenceError}</p>}</details>
    {!items.length && <div className="worker-empty"><strong>{t('Belum ada notifikasi')}</strong><p>{t('Pembaruan tugas akan muncul di sini.')}</p></div>}
    <div className="worker-list">{items.map(item=><article className={`worker-card notification ${item.is_read?'':'unread'}`} key={item.id}><div className="plan-top"><div><strong>{t(notificationLabels[item.type] || 'Pembaruan tugas')}</strong><p>{item.instruction || t('Tugas')}</p></div>{!item.is_read && <span className="unread-dot" aria-label={t('Belum dibaca')}/>}</div><div className="worker-meta">{new Date(item.occurred_at).toLocaleString(dateLocale)}</div>{item.type==='task.failed.v1' && item.task_result?.error && <p className="worker-failure">{item.task_result.error}</p>}{item.type==='task.escalated.v1' && item.data?.message && <p>{item.data.message}</p>}<div className="actions">{!item.is_read && <button className="secondary" onClick={()=>onRead(item)}>{t('Tandai dibaca')}</button>}{!item.archived && ['completed','failed','cancelled'].includes(item.task_status) && <button className="secondary" onClick={()=>onRerun({id:item.task_id})}>{t('Jalankan ulang')}</button>}</div></article>)}</div>
  </div>;
}

function ConfirmDialog({ config, onClose }) {
  const {t}=useLanguage();
  const dialog = useRef(null);
  useEffect(() => { dialog.current?.showModal(); return () => { if (dialog.current?.open) dialog.current.close(); }; }, []);
  return <dialog className="confirm-dialog" ref={dialog} onCancel={e=>{e.preventDefault();onClose();}} aria-labelledby="confirm-title" aria-describedby="confirm-description"><div className="confirm-content"><div className="confirm-icon" aria-hidden="true">!</div><h2 id="confirm-title">{t(config.title)}</h2><p id="confirm-description">{t(config.description)}</p><div className="confirm-actions"><button className="secondary" autoFocus onClick={onClose}>{t('Batal')}</button><button className="danger-button" onClick={()=>{onClose();config.onConfirm();}}>{t(config.confirmLabel || 'Hapus')}</button></div></div></dialog>;
}

const sourceEventLabels = {'media.vision':'Hasil analisis gambar','media.audio':'Hasil analisis audio'};
const sourceKindLabels = {iot:'IoT / sensor',camera:'Kamera',service:'Layanan'};
const humanFieldLabels = {summary:'Ringkasan',count:'Perkiraan jumlah',uncertain:'Kepastian',note:'Catatan',message:'Pesan',status:'Status',reason:'Alasan',action:'Tindakan'};
const publicSourceGroups = [
  {id:'bmkg',name:'Feed data publik BMKG',provider:'BMKG',country:'Indonesia',type:'iot',description:'Prakiraan cuaca dan laporan gempa dari feed resmi BMKG.',fields:['cuaca','suhu','kelembapan','angin','magnitudo gempa','lokasi','laporan gempa dirasakan'],sources:['Cuaca Kemayoran (BMKG)','Gempa Terbaru (BMKG)','Gempa Dirasakan (BMKG)'],feeds:['Cuaca Kemayoran','Gempa terbaru','Gempa dirasakan']},
  {id:'dki-cctv',name:'CCTV publik DKI Jakarta',provider:'BaliTower / Jakarta',country:'Indonesia',type:'camera',description:'Dua feed kamera lalu lintas publik dengan analisis gambar berkala.',fields:['lalu lintas','kondisi jalan','cuplikan kamera'],sources:['CCTV Publik Gatot Subroto','CCTV Publik Gerbang Pemuda'],feeds:['Gatot Subroto','Gerbang Pemuda']},
  {id:'open-meteo',name:'Prakiraan cuaca global',provider:'Open-Meteo',country:'Global',type:'iot',description:'Data prakiraan cuaca tanpa kunci API untuk beberapa kota.',fields:['suhu','kelembapan','curah hujan','kecepatan angin'],sources:['Cuaca Jakarta (Open-Meteo)','Cuaca Singapura (Open-Meteo)','Cuaca Tokyo (Open-Meteo)'],feeds:['Jakarta','Singapura','Tokyo']},
  {id:'usgs',name:'Aktivitas gempa global',provider:'USGS',country:'Global',type:'iot',description:'Feed gempa signifikan dan aktivitas gempa terbaru di seluruh dunia.',fields:['magnitudo','lokasi','kedalaman','waktu gempa'],sources:['Gempa Signifikan Global (USGS)','Gempa 24 Jam Global (USGS)'],feeds:['Gempa signifikan 30 hari','Gempa 24 jam']},
];
function ChatReply({ content }) {
  const {language,t,dateLocale}=useLanguage();
  let value;
  try {
    const candidate = content.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
    value = JSON.parse(candidate);
  } catch { return <>{content}</>; }
  if (!value || typeof value !== 'object') return <>{String(value)}</>;
  const nested = value.data && typeof value.data === 'object' && !Array.isArray(value.data) ? value.data : null;
  const rows = Object.entries(nested ? {...value, ...nested} : value).filter(([k,v]) => k !== 'data' && v != null && v !== '');
  return <div className="chat-structured">{rows.map(([key,v]) => {
    let shown = key==='uncertain' ? t(v ? 'Belum pasti' : 'Cukup yakin') : typeof v === 'object' ? JSON.stringify(v) : String(v);
    if (key === 'event_type') shown = t(({'media.vision':'Hasil analisis gambar','media.audio':'Hasil analisis audio'})[v] || v);
    if (key === 'received_at') { const date = new Date(v); if (!Number.isNaN(date.getTime())) shown = date.toLocaleString(dateLocale); }
    return <p key={key}><strong>{t(humanFieldLabels[key] || ({event_type:'Jenis hasil',received_at:'Waktu pemeriksaan'})[key] || key.replaceAll('_',' '))}:</strong> {shown}</p>;
  })}</div>;
}
function SourceEventContent({ item }) {
  const {t}=useLanguage();
  const p = item.payload || {};
  if (item.event_type === 'media.vision' || item.event_type === 'media.audio') return <div className="event-human">
    {p.summary && <p>{p.summary}</p>}
    {p.count != null && <p><strong>{t('Perkiraan jumlah:')}</strong> {p.count}</p>}
    {p.uncertain && <p className="event-caveat">{t('Hasil ini belum pasti; AI tidak dapat memastikan jawabannya.')}</p>}
    {p.note && <p className="event-caveat">{p.note}</p>}
    {!p.summary && <p>{t('Ringkasan analisis tidak tersedia.')}</p>}
  </div>;
  return <pre>{JSON.stringify(p,null,2)}</pre>;
}

function numericFields(value, prefix='data', depth=0) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || depth > 4 || value.uncertain === true) return [];
  return Object.entries(value).flatMap(([key, item]) => {
    const path = `${prefix}.${key}`;
    if (typeof item === 'number' && Number.isFinite(item)) return [{path, value:item}];
    return numericFields(item, path, depth + 1);
  });
}

function SourceTrend({events}) {
  const {t}=useLanguage();
  const valuesByField = new Map();
  [...events].reverse().forEach(event => numericFields(event.payload).forEach(({path,value}) => {
    if (!valuesByField.has(path)) valuesByField.set(path, []);
    valuesByField.get(path).push({value, at:event.received_at});
  }));
  const series = [...valuesByField.entries()].find(([,items]) => items.length >= 2);
  if (!series) return <p className="source-trend-empty">{t('Tren muncul setelah ada sedikitnya dua observasi numerik dengan field yang sama.')}</p>;
  const [field,items] = series;
  const min = Math.min(...items.map(item=>item.value)), max = Math.max(...items.map(item=>item.value));
  const spread = max-min || 1;
  const points = items.map((item,index)=>`${items.length===1?50:index/(items.length-1)*100},${38-(item.value-min)/spread*30}`).join(' ');
  return <div className="source-trend"><div><strong>{t(field)}</strong><span>{items[items.length-1].value} · {items.length} {t('observasi')}</span></div><svg viewBox="0 0 100 42" role="img" aria-label={`${field}: ${items.map(item=>item.value).join(', ')}`}><polyline points={points} fill="none" stroke="currentColor" strokeWidth="2.5" vectorEffect="non-scaling-stroke"/></svg><small>{new Date(items[0].at).toLocaleString()} → {new Date(items[items.length-1].at).toLocaleString()}</small><small>{t('Angka berasal dari payload sumber; observasi media yang tidak pasti tidak disertakan.')}</small></div>;
}

async function downloadExport(path, filename) {
  const response = await fetch(path);
  if (!response.ok) throw new Error('Ekspor tidak dapat diunduh.');
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href=url; link.download=filename; link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function SourceCard({source,mediaSettings,dateLocale,onView,onStream,onEditMedia,onEdit,onToggle,onAutomation,onRemove,onMediaChange,onSaveMedia,onCancelMedia}) {
  const {t}=useLanguage();
  const active=source.status==='active';const lastSeen=source.last_seen?new Date(source.last_seen):null;
  const health=source.health?.state||'unknown';const healthLabel={recent:'Data terbaru',waiting:'Menunggu data',delayed:'Terlambat',disabled:'Nonaktif',unknown:'Status tidak diketahui'}[health];
  const automated=source.automation_enabled===true;
  return <article className="worker-card source-card" key={source.id}><div className="source-card-header"><span className="source-kind-icon"><Icon name={source.kind==='camera'?'camera':source.kind==='iot'?'thermometer':'plug'} size={19}/></span><span className={`source-status ${health==='recent'?'active':health==='delayed'?'delayed':'disabled'}`}><i/>{t(healthLabel)}</span></div><div className="source-card-title"><span>{t(sourceKindLabels[source.kind]||source.kind)}</span><h3 title={t(source.name)}>{t(source.name)}</h3></div><div className="source-card-meta"><span>{lastSeen?t('Data terakhir diterima'):t('Belum ada data')}</span>{lastSeen&&<time dateTime={lastSeen.toISOString()}>{lastSeen.toLocaleString(dateLocale)}</time>}</div><div className="source-card-meta"><span>{t('Target kirim')}</span><time>{source.expected_interval_seconds?safeIntervalLabel(source.expected_interval_seconds,t):t('Tidak diketahui')}</time></div><div className="source-card-actions"><button className="primary" onClick={()=>onView(source,'data')}>{t('Get Data')}</button>{source.kind==='camera'&&<button className="secondary" onClick={()=>onStream(source,'stream')}>{t('Live Streaming')}</button>}{['camera','iot'].includes(source.kind)&&<><label className="automation-interval">{t('Interval otomasi')}<select aria-label={t('Interval otomasi')} value={source.automation_interval_seconds||30} onChange={e=>onAutomation(source,automated,true,Number(e.target.value))}><option value={5}>5 {t('detik')}</option><option value={10}>10 {t('detik')}</option><option value={30}>30 {t('detik')}</option><option value={60}>60 {t('detik')}</option></select></label><button className={automated?'secondary':'primary'} onClick={()=>onAutomation(source,!automated,false,source.automation_interval_seconds||30)}>{t(automated?'Matikan otomasi':'Aktifkan otomasi')}</button></>}<button className="secondary" onClick={()=>onEditMedia(source)}>{t('Atur media')}</button><button className="secondary" onClick={()=>onEdit(source)}>{t('Ubah')}</button><button className="secondary" onClick={()=>onToggle(source)}>{t(active?'Nonaktifkan':'Aktifkan')}</button><button className="text-button" onClick={()=>onRemove(source)}>{t('Hapus')}</button></div>{mediaSettings?.id===source.id&&<form className="media-settings" onSubmit={onSaveMedia}><p>{t('Media yang diaktifkan akan dikirim ke Baseten untuk dianalisis. Aktifkan hanya sesuai kebutuhan.')}</p><label><input type="checkbox" checked={mediaSettings.vision_enabled} onChange={e=>onMediaChange({...mediaSettings,vision_enabled:e.target.checked})}/> {t('Analisis gambar')}</label><textarea aria-label={t('Pertanyaan tentang gambar')} maxLength={500} required value={mediaSettings.vision_prompt} onChange={e=>onMediaChange({...mediaSettings,vision_prompt:e.target.value})}/><label><input type="checkbox" checked={mediaSettings.audio_enabled} onChange={e=>onMediaChange({...mediaSettings,audio_enabled:e.target.checked})}/> {t('Analisis audio')}</label><textarea aria-label={t('Pertanyaan tentang audio')} maxLength={500} required value={mediaSettings.audio_prompt} onChange={e=>onMediaChange({...mediaSettings,audio_prompt:e.target.value})}/><div className="actions"><button className="primary">{t('Simpan perubahan')}</button><button type="button" className="secondary" onClick={onCancelMedia}>{t('Batal')}</button></div></form>}</article>;
}

function PublicSourcesCatalog({sources,bmkgLocations=[],cctvSources=[],locationsLoading=false,compact=false,onConnect,connecting,credential,onDismissCredential,onBrowse,onView,onEditMedia,onEdit,onToggle,onAutomation,onRemove,mediaSettings,onMediaChange,onSaveMedia,onCancelMedia}) {
  const {t}=useLanguage();
  const [copyStatus,setCopyStatus]=useState('');
  const [search,setSearch]=useState('');
  const [typeFilter,setTypeFilter]=useState('all');
  const [countryFilter,setCountryFilter]=useState('all');
  const [availabilityFilter,setAvailabilityFilter]=useState('all');
  const [showCount,setShowCount]=useState(24);
  useEffect(()=>setShowCount(24),[search,typeFilter,countryFilter,availabilityFilter]);
  const bmkgGroups=bmkgLocations.map(location=>({id:`bmkg-${location.adm4_code}`,adm4_code:location.adm4_code,name:`Cuaca ${location.name}, ${location.regency}`,provider:'BMKG',country:location.country,type:'iot',description:`Prakiraan cuaca kelurahan/desa di ${location.district}, ${location.regency}, ${location.province}.`,fields:['suhu','kelembapan','curah hujan','kondisi cuaca','kecepatan angin'],sources:[location.source_name],feeds:[location.district,location.regency,location.province]}));
  const cctvGroups=cctvSources.map(camera=>({id:`public-cctv-${camera.catalog_id}`,cctv_catalog_id:camera.catalog_id,name:camera.name,provider:camera.provider,country:camera.country,type:'camera',description:`Kamera publik ${camera.address||camera.city}, ${camera.province}.`,fields:['tayangan kamera','kondisi jalan','cuplikan kamera'],sources:[camera.source_name],feeds:[camera.address,camera.area,camera.city,camera.province].filter(Boolean)}));
  const catalogGroups=[...publicSourceGroups,...bmkgGroups,...cctvGroups];
  const countries=[...new Set(catalogGroups.map(group=>group.country))].sort();
  const visible=catalogGroups.filter(group=>{
    const found=group.sources.filter(name=>sources.some(source=>source.name===name));
    const availability=found.length===group.sources.length?'connected':found.length?'partial':'available';
    const text=[group.name,group.provider,group.country,group.description,group.adm4_code,...group.fields,...group.feeds].join(' ').toLocaleLowerCase();
    return (!search||text.includes(search.trim().toLocaleLowerCase()))
      && (typeFilter==='all'||group.type===typeFilter)
      && (countryFilter==='all'||group.country===countryFilter)
      && (availabilityFilter==='all'||availability===availabilityFilter);
  });
  const groupState=group=>{const count=group.sources.filter(name=>sources.some(source=>source.name===name)).length;return {count,state:count===group.sources.length?'connected':count?'partial':'available'};};
  async function copyConfig(){try{await navigator.clipboard.writeText(credential.config);setCopyStatus(t('Konfigurasi tersalin.'));}catch{setCopyStatus(t('Salin konfigurasi secara manual.'));}}
  return <section className={`public-catalog ${compact?'compact':''}`}>
    {!compact&&<div className="public-catalog-filters"><label className="source-search"><Icon name="search" size={17}/><input type="search" value={search} onChange={event=>setSearch(event.target.value)} placeholder={t('Cari nama, penyedia, atau field')} aria-label={t('Cari sumber publik')}/></label><label><span>{t('Jenis')}</span><select value={typeFilter} onChange={event=>setTypeFilter(event.target.value)}><option value="all">{t('Semua jenis')}</option><option value="iot">IoT</option><option value="camera">{t('Kamera')}</option></select></label><label><span>{t('Negara')}</span><select value={countryFilter} onChange={event=>setCountryFilter(event.target.value)}><option value="all">{t('Semua negara')}</option>{countries.map(country=><option key={country}>{country}</option>)}</select></label><label><span>{t('Ketersediaan')}</span><select value={availabilityFilter} onChange={event=>setAvailabilityFilter(event.target.value)}><option value="all">{t('Semua')}</option><option value="available">{t('Belum terhubung')}</option><option value="partial">{t('Sebagian terhubung')}</option><option value="connected">{t('Terhubung')}</option></select></label></div>}
    {locationsLoading&&<div className="worker-empty"><strong>{t('Memuat lokasi BMKG…')}</strong></div>}
    {!locationsLoading&&!visible.length?<div className="worker-empty"><strong>{t('Sumber publik tidak ditemukan')}</strong><p>{t('Coba ubah pencarian atau filter.')}</p></div>:!locationsLoading&&<><div className="public-catalog-grid source-card-grid">{(compact?visible.slice(0,2):visible.slice(0,showCount)).map(group=>{const {state}=groupState(group);const canConnect=group.id==='dki-cctv'?state==='available':state!=='connected';const connected=sources.filter(source=>group.sources.includes(source.name));return <div className="public-source-group" key={group.id}>{connected.map(source=><SourceCard key={source.id} source={source} mediaSettings={mediaSettings} onView={onView} onStream={onView} onEditMedia={onEditMedia} onEdit={onEdit} onToggle={onToggle} onAutomation={onAutomation} onRemove={onRemove} onMediaChange={onMediaChange} onSaveMedia={onSaveMedia} onCancelMedia={onCancelMedia}/>)}{state!=='connected'&&<article className="worker-card source-card public-source-card"><div className="source-card-header"><span className="source-kind-icon"><Icon name={group.type==='iot'?'thermometer':'camera'} size={19}/></span><span className={`source-status ${state==='partial'?'delayed':'disabled'}`}><i/>{t(state==='partial'?'Sebagian terhubung':'Tersedia')}</span></div><div className="source-card-title"><span>{t(group.type==='iot'?'IoT / sensor':'Kamera')} · {t(group.country)}</span><h3 title={t(group.name)}>{t(group.name)}</h3></div><p>{t(group.description)}</p><div className="source-card-meta"><span>{t('Penyedia')}</span><time>{t(group.provider)}</time></div><div className="public-source-feeds"><strong>{t('Feed')}</strong>{group.feeds.map(feed=><span key={feed}>{t(feed)}</span>)}</div><div className="public-source-fields"><strong>{t('Field')}</strong><span>{group.fields.map(field=>t(field)).join(' · ')}</span></div><div className="source-card-actions public-source-card-actions"><button className={canConnect?'primary':'secondary'} type="button" disabled={!canConnect||connecting===group.id} onClick={()=>onConnect(group)}>{t(connecting===group.id?'Menyambungkan…':state==='partial'?'Hubungkan sumber tersisa':`Hubungkan ${group.provider}`)}</button>{group.id==='dki-cctv'&&state==='partial'&&<small>{t('Sebagian feed sudah ada. Hapus sumber CCTV yang ada sebelum membuat paket lagi.')}</small>}</div></article>}</div>;})}</div>{visible.length>showCount&&!compact&&<button className="secondary public-load-more" type="button" onClick={()=>setShowCount(count=>Math.min(count+24,visible.length))}>{t('Tampilkan 24 lokasi berikutnya')} · {visible.length-showCount}</button>}</>}
    {credential&&<section className="credential public-source-credential"><strong>{t('Sumber publik siap')}</strong><p>{t('Simpan token gateway sekarang. Token hanya ditampilkan sekali.')}</p><p>{t('Sumber publik dibuat nonaktif. Aktifkan dari kartunya sebelum menjalankan gateway.')}</p><label>{t('Konfigurasi gateway')}<textarea readOnly rows={Math.min(10,credential.config.split('\n').length)} value={credential.config} onFocus={event=>event.target.select()}/></label><div className="actions"><button className="secondary" type="button" onClick={copyConfig}>{t('Salin konfigurasi')}</button><button className="text-button" type="button" onClick={onDismissCredential}>{t('Saya sudah menyimpan token')}</button></div>{copyStatus&&<p role="status">{copyStatus}</p>}</section>}
  </section>;
}

function safeIntervalLabel(seconds,t){
  if(seconds%3600===0)return `${seconds/3600} ${t('jam')}`;
  if(seconds%60===0)return `${seconds/60} ${t('menit')}`;
  return `${seconds} ${t('detik')}`;
}

function SourceDetailsDialog({ source, events, loading, error, requestMessage, requestState, previewUrl, previewStatus, onRequestData, onClose, mode, onRefresh }) {
  const {t,dateLocale}=useLanguage();
  const dialog = useRef(null);
  useEffect(() => { dialog.current?.showModal(); return () => { if (dialog.current?.open) dialog.current.close(); }; }, []);
  const preview = source.name === 'Kamera Gudang' ? warehouseDemo : source.name === 'Kamera Area Staf' ? staffCameraDemo : null;
  const publicStream = publicCctvFeeds[source.name];
  const staleAfter=Math.max(300,(source.expected_interval_seconds||300)*2);
  return <dialog className="source-details-dialog" ref={dialog} onCancel={event=>{event.preventDefault();onClose();}} aria-labelledby="source-details-title">
    <div className="source-dialog-header"><div><span className="source-card-kind">{t(sourceKindLabels[source.kind] || source.kind)}</span><h2 id="source-details-title">{mode==='stream'?t('Live Streaming'):t('Get Data')} · {t(source.name)}</h2></div><button className="icon-button" type="button" onClick={onClose} aria-label={t('Tutup detail sumber')}>×</button></div>
    <div className="source-dialog-meta"><span className={`source-status ${source.status==='active'?'active':'disabled'}`}><i/>{t(source.status==='active'?'Aktif':'Nonaktif')}</span><span>{source.last_seen?`${t('Data terakhir')} ${new Date(source.last_seen).toLocaleString(dateLocale)}`:t('Belum menerima data')}</span></div>
    <div className="source-live-status"><span className="source-live-pulse"/>{t('Riwayat dimuat manual.')}<button className="text-button" type="button" onClick={onRefresh}>{t('Perbarui sekarang')}</button></div>
    {mode==='stream' && source.kind==='camera' && <section className="source-live-preview" aria-label={t('Live Streaming')}>
      {publicStream ? <div className="public-cctv-inline-player"><iframe src={publicStream} title={t(source.name)} allow="autoplay; fullscreen; picture-in-picture" allowFullScreen referrerPolicy="no-referrer"/><span className="source-live-badge">{t('CCTV Publik DKI Jakarta · tayangan langsung')}</span></div> : preview ? <><div className="source-live-image-wrap"><img src={preview} alt={t(source.name)} /><span className="source-live-badge">{t('Simulasi')}</span></div><p>{t('Gambar demo; data perangkat diperbarui berkala.')}</p></> : <p>{t('Streaming video langsung belum tersedia untuk sumber ini. Event terbaru tetap diperbarui berkala.')}</p>}
      <small>{publicStream?t('Kamera publik mengirim cuplikan untuk analisis AI berkala; player langsung mengikuti portal sumber.'):t('Sumber mengirim cuplikan berkala, bukan video langsung.')}</small>
    </section>}
    {requestMessage&&<p className="source-request-notice" role="status">{t(requestMessage)}</p>}
    {mode==='data'&&source.kind==='camera'&&requestState==='requesting'&&!previewUrl&&<section className="source-capture-loading" role="status" aria-live="polite"><span className="loading-spinner" aria-hidden="true"/><div><strong>{t('Mengambil gambar dari kamera…')}</strong><span>{t('Menunggu kamera mengirim gambar. Proses ini bisa memerlukan beberapa saat.')}</span></div></section>}
    {mode==='data'&&source.kind==='camera'&&previewUrl&&<section className={`source-capture-preview ${previewStatus==='fetching'?'is-fetching':''}`} aria-label={t('Cuplikan kamera')} aria-busy={previewStatus==='fetching'}><div className="source-capture-image"><img src={previewUrl} alt={`${t('Cuplikan kamera')} · ${t(source.name)}`}/>{previewStatus==='fetching'&&<div className="source-capture-overlay" role="status"><span className="loading-spinner" aria-hidden="true"/>{t('Memperbarui cuplikan…')}</div>}</div><div><strong>{t('Cuplikan kamera')}</strong><span>{t(previewStatus==='fetching'?'Memperbarui cuplikan…':previewStatus==='failed'?'Analisis AI gagal; cuplikan tetap tersedia.':previewStatus==='analyzing'?'Cuplikan diterima, menunggu analisis…':previewStatus==='stale'?'Pengambilan terbaru belum berhasil; cuplikan sebelumnya ditampilkan.':'Data terbaru')}</span></div></section>}
    {mode==='data'&&source.kind==='camera'&&!previewUrl&&requestState!=='requesting'&&previewStatus==='unavailable'&&<section className="source-capture-unavailable" role="status"><strong>{t('Gambar belum diterima. Periksa gateway atau feed, lalu coba lagi.')}</strong></section>}
    <section className="source-event-list" aria-label={t('Riwayat data sumber')}><div className="source-trend-heading"><h3>{t('Tren sensor')}</h3><div className="actions"><button className="text-button" type="button" onClick={()=>downloadExport(`/v1/sources/${encodeURIComponent(source.id)}/events/export?format=csv`,`kanca-${source.id}-events.csv`).catch(error=>window.alert(error.message))}>{t('Ekspor CSV')}</button><button className="text-button" type="button" onClick={()=>downloadExport(`/v1/sources/${encodeURIComponent(source.id)}/events/export?format=json`,`kanca-${source.id}-events.json`).catch(error=>window.alert(error.message))}>{t('Ekspor JSON')}</button></div></div><SourceTrend events={events}/><h3>{t('Data terbaru')}</h3>{requestState==='requesting'&&!events.length?<p className="source-dialog-empty" role="status">{t('Mengambil data satu kali…')}</p>:loading ? <p className="source-dialog-empty">{t('Memuat data…')}</p> : error ? <p className="source-dialog-empty error">{error}</p> : !events.length&&requestState==='timeout' ? <p className="source-dialog-empty error">{t('Belum menerima data baru. Periksa gateway dan feed, lalu coba Get Data lagi.')}</p> : !events.length ? <p className="source-dialog-empty">{t('Belum ada data yang diterima dari sumber ini.')}</p> : events.map(item=>{const observedAt=new Date(item.received_at);const stale=Date.now()-observedAt.getTime()>staleAfter*1000;return <article className="source-event-card" key={item.id}><div className="source-event-heading"><strong>{t(sourceEventLabels[item.event_type] || item.event_type)}</strong><time dateTime={item.received_at}>{observedAt.toLocaleString(dateLocale)}</time></div>{stale&&<p className="event-caveat">{t('Observasi ini sudah melewati batas kesegaran sumber.')}</p>}<SourceEventContent item={item}/></article>;})}</section>
    <div className="source-dialog-actions">{mode==='data'&&['camera','iot'].includes(source.kind)&&<button className="primary" type="button" onClick={()=>onRequestData(source)} disabled={requestState==='requesting'} aria-busy={requestState==='requesting'}>{requestState==='requesting'&&<span className="loading-spinner" aria-hidden="true"/>}{t(requestState==='requesting'?'Mengambil data…':events.length||previewUrl?'Get Data lagi':'Get Data')}</button>}<button className="secondary" type="button" onClick={onClose}>{t('Tutup')}</button></div>
  </dialog>;
}

function WebhookPanel({ requestConfirm, credential, onCreated }) {
  const {t,dateLocale}=useLanguage();
  const [url, setUrl] = useState('');
  const [subscriptions, setSubscriptions] = useState([]);
  const [deliveries, setDeliveries] = useState([]);
  const [statusFilter, setStatusFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [copyMessage, setCopyMessage] = useState('');
  const [creating, setCreating] = useState(false);
  const webhookTypes=['task.created.v1','task.approval_requested.v1','task.approved.v1','task.started.v1','task.checked.v1','task.completed.v1','task.failed.v1','task.escalated.v1','task.cancelled.v1','task.paused.v1','task.resumed.v1','task.archived.v1','task.action_taken.v1','source.event.v1'];
  const [selectedTypes,setSelectedTypes]=useState(webhookTypes);
  const [editingTypes,setEditingTypes]=useState(null);
  const creatingRef = useRef(false);
  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [items, attempts] = await Promise.all([api('/v1/webhook-subscriptions'), api('/v1/webhook-deliveries')]);
      setSubscriptions(items); setDeliveries(attempts); setError('');
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  async function create(event) {
    event.preventDefault(); if (creatingRef.current) return; creatingRef.current = true; setCreating(true); setError('');
    try {
      const result = await api('/v1/webhook-subscriptions', {method:'POST', body:JSON.stringify({url:url.trim(),event_types:selectedTypes})});
      onCreated(result); setUrl(''); await refresh();
    } catch (err) { setError(err.message); } finally { creatingRef.current = false; setCreating(false); }
  }
  function disable(subscription) {
    requestConfirm({title:t('Nonaktifkan webhook?'),description:t('Kanca tidak akan mengirim event baru ke {url}. Riwayat pengiriman tetap tersimpan.').replace('{url}',subscription.url),confirmLabel:t('Nonaktifkan'),onConfirm:async()=>{try{await api(`/v1/webhook-subscriptions/${encodeURIComponent(subscription.id)}`,{method:'DELETE'});await refresh();}catch(err){setError(err.message);}}});
  }
  async function copy(value, label) {
    try { await navigator.clipboard.writeText(value); setCopyMessage(`${label} disalin.`); }
    catch { setCopyMessage(`Salin ${label.toLowerCase()} secara manual.`); }
  }
  const visibleDeliveries = deliveries.filter(item => statusFilter==='all' || item.status===statusFilter);
  const statusLabels = {pending:'Menunggu',sending:'Mengirim',delivered:'Terkirim',failed:'Gagal'};
  const format = (template, values) => Object.entries(values).reduce((text,[key,value])=>text.replace(`{${key}}`,value),t(template));
  return <div className="webhook-panel">
    <div className="webhook-intro"><div><div className="eyebrow">{t('KELUAR')}</div><h2>Webhook</h2><p>{t('Kirim event Kanca ke endpoint HTTPS milikmu. Secret hanya ditampilkan saat webhook dibuat.')}</p></div></div>
    <form className="webhook-form" onSubmit={create}><label htmlFor="webhook-url">{t('URL endpoint')}</label><div className="webhook-form-row"><input id="webhook-url" type="url" required maxLength={2048} value={url} onChange={event=>setUrl(event.target.value)} placeholder="https://example.com/webhook"/><button className="primary" disabled={creating}>{t(creating?'Menambahkan…':'Tambah webhook')}</button></div><p>{t('Endpoint harus menggunakan HTTPS, port 443, dan alamat IP publik.')}</p><details className="notification-preferences"><summary>{t('Pilih event webhook')}</summary><div className="preference-options">{webhookTypes.map(kind=><label key={kind}><input type="checkbox" checked={selectedTypes.includes(kind)} onChange={event=>setSelectedTypes(current=>event.target.checked?[...current,kind]:current.filter(item=>item!==kind))}/>{kind}</label>)}</div></details></form>
    {credential && <section className="webhook-secret" aria-live="polite"><div><strong>{t('Webhook berhasil dibuat')}</strong><p>{t('Simpan secret ini sekarang. Kanca tidak dapat menampilkannya lagi setelah bagian ini ditutup.')}</p></div><label>{t('Signing secret')}<input readOnly value={credential.secret} onFocus={event=>event.target.select()}/></label><div className="webhook-secret-actions"><button className="secondary" type="button" onClick={()=>copy(credential.secret,'Secret')}>{t('Salin secret')}</button><button className="text-button" type="button" onClick={()=>{onCreated(null);setCopyMessage('');}}>{t('Saya sudah menyimpan')}</button></div>{copyMessage && <p className="webhook-copy-message" role="status">{t(copyMessage)}</p>}</section>}
    {error && <p className="error" role="alert">{error}</p>}
    <section className="webhook-subscriptions"><div className="webhook-section-heading"><div><h3>{t('Endpoint terdaftar')}</h3><p>{subscriptions.filter(item=>item.active).length} {t('aktif')} · {subscriptions.length} {t('total')}</p></div><button className="secondary" type="button" onClick={refresh} disabled={loading}>{t('Muat ulang')}</button></div>
      {loading && !subscriptions.length ? <p className="webhook-empty">{t('Memuat endpoint…')}</p> : !subscriptions.length ? <p className="webhook-empty">{t('Belum ada webhook. Tambahkan URL endpoint di atas untuk menerima event.')}</p> : <div className="webhook-subscription-list">{subscriptions.map(subscription=><article className="webhook-subscription" key={subscription.id}><div className="webhook-subscription-copy"><span className={`source-status ${subscription.active?'active':'disabled'}`}><i/>{t(subscription.active?'Aktif':'Nonaktif')}</span><strong title={subscription.url}>{subscription.url}</strong><span>{t('Dibuat')} {new Date(subscription.created_at).toLocaleString(dateLocale)}</span><span>{t('Jenis event')}: {(subscription.event_types||['*']).join(', ')}</span>{editingTypes?.id===subscription.id&&<div className="preference-options">{webhookTypes.map(kind=><label key={kind}><input type="checkbox" checked={editingTypes.types.includes(kind)} onChange={event=>setEditingTypes({...editingTypes,types:event.target.checked?[...editingTypes.types,kind]:editingTypes.types.filter(item=>item!==kind)})}/>{kind}</label>)}<button className="secondary" type="button" onClick={async()=>{try{await api(`/v1/webhook-subscriptions/${encodeURIComponent(subscription.id)}/event-types`,{method:'PUT',body:JSON.stringify({event_types:editingTypes.types})});setEditingTypes(null);await refresh();}catch(err){setError(err.message);}}}>{t('Simpan perubahan')}</button></div>}</div>{subscription.active && <div className="actions"><button className="secondary" type="button" onClick={()=>setEditingTypes({id:subscription.id,types:subscription.event_types?.includes('*')?webhookTypes:[...(subscription.event_types||[])]})}>{t('Atur event')}</button><button className="secondary" type="button" onClick={()=>disable(subscription)}>{t('Nonaktifkan')}</button></div>}</article>)}</div>}
    </section>
    <section className="webhook-deliveries"><div className="webhook-section-heading"><div><h3>{t('Riwayat pengiriman')}</h3><p>{t('Maksimal 100 pengiriman terbaru')}</p></div><label className="webhook-status-filter"><span>{t('Status')}</span><select value={statusFilter} onChange={event=>setStatusFilter(event.target.value)} aria-label={t('Filter status pengiriman')}><option value="all">{t('Semua')}</option><option value="pending">{t('Menunggu')}</option><option value="sending">{t('Mengirim')}</option><option value="delivered">{t('Terkirim')}</option><option value="failed">{t('Gagal')}</option></select></label></div>
      {!visibleDeliveries.length ? <p className="webhook-empty">{t(deliveries.length?'Tidak ada pengiriman dengan status ini.':'Belum ada event untuk dikirim.')}</p> : <div className="webhook-delivery-list">{visibleDeliveries.slice(0,30).map(item=>{const endpoint=subscriptions.find(subscription=>subscription.id===item.subscription_id)?.url || t('Endpoint webhook');return <article className="webhook-delivery" key={item.id}><span className={`delivery-state ${item.status}`}><i/>{t(statusLabels[item.status] || item.status)}</span><div className="webhook-delivery-copy"><strong title={endpoint}>{endpoint}</strong><span>{format('{attempts} percobaan',{attempts:item.attempts})} · {item.last_status?`HTTP ${item.last_status}`:t('belum ada respons HTTP')}</span></div></article>;})}</div>}
    </section>
  </div>;
}

function Sources({ sources, onChanged, requestConfirm }) {
  const {t,dateLocale}=useLanguage();
  const [name, setName] = useState('');
  const [kind, setKind] = useState('iot');
  const [expectedInterval,setExpectedInterval]=useState(300);
  const [editing, setEditing] = useState(null);
  const [credential, setCredential] = useState(null);
  const [selected, setSelected] = useState(null);
  const [events, setEvents] = useState([]);
  const [eventsError, setEventsError] = useState('');
  const [requestMessage,setRequestMessage]=useState('');
  const [requestState,setRequestState]=useState('idle');
  const [previewUrl,setPreviewUrl]=useState('');
  const [previewStatus,setPreviewStatus]=useState('');
  const [publicCredential,setPublicCredential]=useState(null);
  const [bmkgLocations,setBmkgLocations]=useState([]);
  const [cctvSources,setCctvSources]=useState([]);
  const [bmkgLocationsLoading,setBmkgLocationsLoading]=useState(true);
  const [connectingPublic,setConnectingPublic]=useState('');
  const [mediaSettings, setMediaSettings] = useState(null);
  const [error, setError] = useState('');
  const [sourceQuery, setSourceQuery] = useState('');
  const [sourceTypeFilter, setSourceTypeFilter] = useState('all');
  const [sourceStatusFilter, setSourceStatusFilter] = useState('all');
  const [integrationSection, setIntegrationSection] = useState('sources');
  const [webhookCredential, setWebhookCredential] = useState(null);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [dialogMode, setDialogMode] = useState('data');
  const manualSetupRef = useRef(null);
  const nameInputRef = useRef(null);
  const eventsRequest = useRef(0);
  const dataRequest = useRef(0);
  const previewUrlRef = useRef('');
  const previewRequestAtRef = useRef('');
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  useEffect(()=>{let cancelled=false;Promise.allSettled([api('/v1/public-sources/bmkg-weather'),api('/v1/public-sources/cctv')]).then(([locations,cameras])=>{if(cancelled)return;if(locations.status==='fulfilled')setBmkgLocations(locations.value);else setError(locations.reason.message);if(cameras.status==='fulfilled')setCctvSources(cameras.value);else setError(cameras.reason.message);}).finally(()=>{if(!cancelled)setBmkgLocationsLoading(false);});return()=>{cancelled=true;}},[]);
  useEffect(()=>{if(!editing||integrationSection!=='sources'||!manualSetupRef.current)return;manualSetupRef.current.open=true;requestAnimationFrame(()=>{manualSetupRef.current?.scrollIntoView({behavior:'smooth',block:'center'});nameInputRef.current?.focus({preventScroll:true});});},[editing,integrationSection]);
  async function connectPublic(group) {
    if(connectingPublic)return;
    setConnectingPublic(group.id);setError('');setPublicCredential(null);
    try {
      const endpoint=group.cctv_catalog_id?'/v1/sources/public-cctv':group.adm4_code?'/v1/sources/public-bmkg-location':group.id==='bmkg'?'/v1/sources/public-bmkg':group.id==='dki-cctv'?'/v1/sources/public-cctv-pack':'/v1/sources/public-global-pack';
      const result=await api(endpoint,{method:'POST',...((group.adm4_code||group.cctv_catalog_id)?{body:JSON.stringify(group.cctv_catalog_id?{catalog_id:group.cctv_catalog_id}:{adm4_code:group.adm4_code})}:{})});
      const configured=(result.sources||[]).map(source=>group.type==='iot'
        ? {type:'http_json',name:source.name,source_id:source.id,source_token:source.token,http_url:source.http_url,interval_seconds:source.interval_seconds,event_type:source.event_type,on_demand:true}
        : {type:'camera',name:source.name,source_id:source.id,source_token:source.token,camera_url:source.camera_url,interval_seconds:source.interval_seconds,audio_enabled:false,on_demand:true});
      if(configured.length)setPublicCredential({config:JSON.stringify({server_url:window.location.origin,sources:configured},null,2)});
      await onChanged();
    } catch(e) {setError(e.message);}
    finally {setConnectingPublic('');}
  }
  function beginEdit(source) {
    setIntegrationSection('sources');
    setEditing(source);
    setName(source.name);
    setKind(source.kind);
    setExpectedInterval(source.expected_interval_seconds||300);
    setError('');
  }
  function cancelSourceEdit() {
    setEditing(null);setName('');setKind('iot');setExpectedInterval(300);setError('');
    if(manualSetupRef.current)manualSetupRef.current.open=false;
  }
  async function submit(e) { e.preventDefault(); if (submittingRef.current) return; submittingRef.current = true; setSubmitting(true); setError(''); try {
    if (editing) await api(`/v1/sources/${encodeURIComponent(editing.id)}`, {method:'PUT',body:JSON.stringify({name,kind,status:editing.status,expected_interval_seconds:Number(expectedInterval)})});
    else { const result=await api('/v1/sources',{method:'POST',body:JSON.stringify({name,kind,expected_interval_seconds:Number(expectedInterval)})}); setCredential(result); }
    setName('');setKind('iot');setExpectedInterval(300);setEditing(null);if(manualSetupRef.current)manualSetupRef.current.open=false;await onChanged();
  } catch(e) {setError(e.message);} finally {submittingRef.current = false; setSubmitting(false);} }
  async function toggle(source) {try {await api(`/v1/sources/${encodeURIComponent(source.id)}`,{method:'PUT',body:JSON.stringify({name:source.name,kind:source.kind,status:source.status==='active'?'disabled':'active'})});await onChanged();}catch(e){setError(e.message);}}
  async function toggleAutomation(source,enabled,intervalOnly=false,intervalSeconds=source.automation_interval_seconds||30) {try {await api(`/v1/sources/${encodeURIComponent(source.id)}/automation`,{method:'PUT',body:JSON.stringify({enabled,interval_seconds:intervalSeconds})});if(!intervalOnly)setError('');await onChanged();}catch(e){setError(e.message);}}
  function remove(source) {requestConfirm({title:t('Hapus sumber?'),description:t('{name} tidak dapat mengirim data lagi. Riwayatnya tetap tersimpan.').replace('{name}',source.name),onConfirm:async()=>{try{await api(`/v1/sources/${encodeURIComponent(source.id)}`,{method:'DELETE'});if(selected===source.id)closeEvents();await onChanged();}catch(e){setError(e.message);}}});}
  const refreshEvents = useCallback(async (sourceId=selected, initial=false) => {if(!sourceId)return;const request=++eventsRequest.current;if(initial)setEventsLoading(true);try {const result=await api(`/v1/sources/${encodeURIComponent(sourceId)}/events`);if(request===eventsRequest.current){setEvents(result);setEventsError('');}}catch(e){if(request===eventsRequest.current)setEventsError(e.message);}finally{if(request===eventsRequest.current&&initial)setEventsLoading(false);}},[selected]);
  async function requestSourceData(source) {
    const requestNumber=++dataRequest.current;
    if(source.kind==='camera')setPreviewStatus('fetching');
    setRequestState('requesting');setRequestMessage('Permintaan data satu kali dikirim ke gateway. Feed publik tidak dibaca berkala.');setEventsError('');
    try {
      const queued=await api(`/v1/sources/${encodeURIComponent(source.id)}/request-data`,{method:'POST'});
      const requestedAt=Date.parse(queued.requested_at);
      if(requestNumber!==dataRequest.current)return;
      let capturedThisRequest=false;
      let captureStatus='';
      if(source.kind==='camera') {
        try {
          const previewResponse=await fetch(`/v1/sources/${encodeURIComponent(source.id)}/preview`,{cache:'no-store'});
          if(requestNumber!==dataRequest.current)return;
          if(previewResponse.ok) {
            const requestedAtHeader=previewResponse.headers.get('X-Kanca-Request-At')||'';
            const previewAt=Date.parse(requestedAtHeader);
            if(Number.isFinite(previewAt)&&previewAt>=requestedAt) {
              const status=previewResponse.headers.get('X-Kanca-Preview-Status')||'';
              captureStatus=status;
              const objectUrl=URL.createObjectURL(await previewResponse.blob());
              if(requestNumber!==dataRequest.current){URL.revokeObjectURL(objectUrl);return;}
              if(previewUrlRef.current)URL.revokeObjectURL(previewUrlRef.current);
              previewUrlRef.current=objectUrl;
              previewRequestAtRef.current=requestedAtHeader;
              capturedThisRequest=true;
              setPreviewUrl(objectUrl);
              setPreviewStatus(status);
            }
          }
        } catch {
          // The event result may still be available even if an image preview cannot be read.
        }
      }
      const rows=await api(`/v1/sources/${encodeURIComponent(source.id)}/events`);
      if(requestNumber!==dataRequest.current)return;
      setEvents(rows);
      setEventsLoading(false);
      const fresh=rows.some(item=>Date.parse(item.received_at)>=requestedAt&&(source.kind!=='camera'||item.event_type==='media.vision'));
      if(source.kind==='camera'&&!capturedThisRequest)setPreviewStatus(previewUrlRef.current?'stale':'unavailable');
      if(fresh||queued.status==='received'||capturedThisRequest) {
        setRequestState('complete');
        setRequestMessage(capturedThisRequest&&captureStatus==='failed'?'Frame berhasil diambil, tetapi analisis AI gagal. Cuplikannya tetap bisa dilihat; klik Get Data lagi untuk mencoba ulang.':capturedThisRequest&&!fresh?'Gambar baru diterima; analisis AI mungkin masih diproses.':'Data baru diterima.');
        return;
      }
      setRequestState('timeout');
      setRequestMessage('Belum menerima data baru. Periksa gateway dan feed, lalu coba Get Data lagi.');
      if(source.kind==='camera')setPreviewStatus(previewUrlRef.current?'stale':'unavailable');
    } catch(e) {
      if(requestNumber===dataRequest.current){setEventsLoading(false);setRequestState('error');setRequestMessage(e.message||'Permintaan data gagal.');if(source.kind==='camera'&&!previewUrlRef.current)setPreviewStatus('unavailable');}
    }
  }
  async function refreshSourceDetails(source) {
    await refreshEvents(source.id);
    if(source.kind!=='camera')return;
    try {
      const response=await fetch(`/v1/sources/${encodeURIComponent(source.id)}/preview`,{cache:'no-store'});
      if(!response.ok)return;
      const requestedAt=response.headers.get('X-Kanca-Request-At')||'';
      const status=response.headers.get('X-Kanca-Preview-Status')||'';
      if(requestedAt!==previewRequestAtRef.current) {
        const objectUrl=URL.createObjectURL(await response.blob());
        if(previewUrlRef.current)URL.revokeObjectURL(previewUrlRef.current);
        previewUrlRef.current=objectUrl;
        previewRequestAtRef.current=requestedAt;
        setPreviewUrl(objectUrl);
      }
      setPreviewStatus(status);
      if(status==='failed')setRequestMessage('Frame berhasil diambil, tetapi analisis AI gagal. Cuplikannya tetap bisa dilihat; klik Get Data lagi untuk mencoba ulang.');
    } catch {}
  }
  function viewEvents(source, mode='data') {const canRequest=mode==='data'&&['camera','iot'].includes(source.kind);dataRequest.current++;if(previewUrlRef.current)URL.revokeObjectURL(previewUrlRef.current);previewUrlRef.current='';previewRequestAtRef.current='';setPreviewUrl('');setPreviewStatus('');setSelected(source.id);setDialogMode(mode);setEvents([]);setEventsError('');setRequestMessage('');setRequestState('idle');setEventsLoading(!canRequest);if(canRequest)requestSourceData(source);else refreshEvents(source.id,true);}
  function closeEvents() {dataRequest.current++;eventsRequest.current++;if(previewUrlRef.current)URL.revokeObjectURL(previewUrlRef.current);previewUrlRef.current='';previewRequestAtRef.current='';setPreviewUrl('');setPreviewStatus('');setSelected(null);setEvents([]);setEventsError('');setRequestMessage('');setRequestState('idle');setEventsLoading(false);}
  async function editMedia(source) {try{setMediaSettings({id:source.id,...await api(`/v1/sources/${encodeURIComponent(source.id)}/media-settings`)});setError('');}catch(e){setError(e.message);}}
  async function saveMedia(e) {e.preventDefault();try {const {id,...settings}=mediaSettings;await api(`/v1/sources/${encodeURIComponent(id)}/media-settings`,{method:'PUT',body:JSON.stringify(settings)});setMediaSettings(null);setError('');}catch(e){setError(e.message);}}
  const filteredSources = sources.filter(source => {
    const matchesQuery = `${source.name} ${source.kind} ${sourceKindLabels[source.kind] || ''}`.toLowerCase().includes(sourceQuery.trim().toLowerCase());
    return matchesQuery && (sourceTypeFilter === 'all' || source.kind === sourceTypeFilter) && (sourceStatusFilter === 'all' || source.status === sourceStatusFilter);
  });
  const recentSources=sources.filter(source=>source.health?.state==='recent').length;
  const attentionSources=sources.filter(source=>['waiting','delayed','unknown'].includes(source.health?.state)).length;
  const selectedSource = sources.find(source=>source.id===selected);
  const publicSourcesPanel = <div className="source-panel-content public-sources-panel">
    <div className="error source-panel-error" role="alert">{error}</div>
    <PublicSourcesCatalog sources={sources} bmkgLocations={bmkgLocations} cctvSources={cctvSources} locationsLoading={bmkgLocationsLoading} onConnect={connectPublic} connecting={connectingPublic} credential={publicCredential} onDismissCredential={()=>setPublicCredential(null)} onView={viewEvents} onEditMedia={editMedia} onEdit={beginEdit} onToggle={toggle} onAutomation={toggleAutomation} onRemove={remove} mediaSettings={mediaSettings} onMediaChange={setMediaSettings} onSaveMedia={saveMedia} onCancelMedia={()=>setMediaSettings(null)}/>
  </div>;
  return <div className="workers integration-page"><div className="workers-header integration-page-heading"><div><div className="eyebrow">{t('INTEGRASI')}</div><h1>{t('Integrasi')}</h1><p>{t('Kelola sumber data masuk dan webhook untuk event keluar.')}</p></div></div>
    <div className="integration-overview" aria-label={t('Ringkasan integrasi')}>
      <article><span className="integration-overview-icon"><Icon name="plug" size={17}/></span><div><strong>{sources.length}</strong><span>{t('Sumber terdaftar')}</span></div></article>
      <article><span className="integration-overview-icon is-live"><Icon name="check" size={17}/></span><div><strong>{recentSources}</strong><span>{t('Data terbaru')}</span></div></article>
      <article><span className="integration-overview-icon is-attention"><Icon name="clock" size={17}/></span><div><strong>{attentionSources}</strong><span>{t('Perlu perhatian')}</span></div></article>
    </div>
    <div className="integration-tabs" role="tablist" aria-label={t('Jenis integrasi')}>
      <button type="button" role="tab" id="sources-tab" aria-controls="sources-panel" aria-selected={integrationSection==='sources'} className={integrationSection==='sources'?'active':''} onClick={()=>setIntegrationSection('sources')}><span className="integration-tab-icon"><Icon name="plug" size={18}/></span><span className="integration-tab-copy"><strong>{t('Sumber perangkat')}</strong><small>{t('Kamera, IoT, dan layanan')}</small></span><span className="integration-tab-count">{sources.length}</span></button>
      <button type="button" role="tab" id="public-sources-tab" aria-controls="public-sources-panel" aria-selected={integrationSection==='public'} className={integrationSection==='public'?'active':''} onClick={()=>setIntegrationSection('public')}><span className="integration-tab-icon"><Icon name="sun" size={18}/></span><span className="integration-tab-copy"><strong>{t('Public Sources')}</strong><small>{publicSourceGroups.reduce((total,group)=>total+group.sources.length,0)+bmkgLocations.length+cctvSources.length} {t('feed tersedia')}</small></span></button>
      <button type="button" role="tab" id="webhooks-tab" aria-controls="webhooks-panel" aria-selected={integrationSection==='webhooks'} className={integrationSection==='webhooks'?'active':''} onClick={()=>setIntegrationSection('webhooks')}><span className="integration-tab-icon"><Icon name="up" size={18}/></span><span className="integration-tab-copy"><strong>{t('Webhook')}</strong><small>{t('Event keluar')}</small></span></button>
    </div>
    {integrationSection==='webhooks' ? <div id="webhooks-panel" role="tabpanel" aria-labelledby="webhooks-tab"><WebhookPanel requestConfirm={requestConfirm} credential={webhookCredential} onCreated={setWebhookCredential}/></div> : integrationSection==='public' ? <div id="public-sources-panel" role="tabpanel" aria-labelledby="public-sources-tab">{publicSourcesPanel}</div> : <div className="source-panel-content" id="sources-panel" role="tabpanel" aria-labelledby="sources-tab"><>
    <div className="error source-panel-error" role="alert">{error}</div>
    <section className="source-browser" aria-label={t('Daftar sumber integrasi')}>
      <div className="source-browser-heading"><div><h2>{t('Sumber terhubung')}</h2><p>{sources.length} {t('sumber terdaftar')}</p><p className="source-health-note">{t('Status penerimaan memakai waktu event terakhir dan interval harapan; proses gateway tidak diperiksa langsung.')}</p></div><div className="actions"><button className="secondary" type="button" onClick={()=>downloadExport('/v1/events/export?format=csv','kanca-events.csv').catch(error=>window.alert(error.message))}>{t('Ekspor batch event CSV')}</button><button className="secondary" type="button" onClick={()=>downloadExport('/v1/events/export?format=json','kanca-events.json').catch(error=>window.alert(error.message))}>{t('Ekspor batch event JSON')}</button></div></div>
      <div className="source-controls">
        <label className="source-search"><Icon name="search" size={17}/><input type="search" value={sourceQuery} onChange={event=>setSourceQuery(event.target.value)} placeholder={t('Cari nama sumber')} aria-label={t('Cari sumber integrasi')}/></label>
        <div className="source-filter-row"><div className="source-type-filters" role="group" aria-label={t('Filter jenis sumber')}>{[['all','Semua'],['iot','IoT / sensor'],['camera','Kamera'],['service','Layanan']].map(([value,label])=><button type="button" key={value} className={sourceTypeFilter===value?'active':''} aria-pressed={sourceTypeFilter===value} onClick={()=>setSourceTypeFilter(value)}>{t(label)}</button>)}</div><label className="source-status-filter"><span>{t('Status')}</span><select value={sourceStatusFilter} onChange={event=>setSourceStatusFilter(event.target.value)} aria-label={t('Filter status sumber')}><option value="all">{t('Semua')}</option><option value="active">{t('Aktif')}</option><option value="disabled">{t('Nonaktif')}</option></select></label></div>
      </div>
      {!sources.length ? <div className="worker-empty source-empty"><strong>{t('Belum ada sumber')}</strong><p>{t('Tambahkan kamera, sensor, atau layanan untuk mulai menerima data.')}</p></div> : !filteredSources.length ? <div className="worker-empty source-empty"><strong>{t('Sumber tidak ditemukan')}</strong><p>{t('Coba ubah kata pencarian atau filter yang dipilih.')}</p></div> : <div className="source-card-grid">{filteredSources.map(source=><SourceCard key={source.id} source={source} mediaSettings={mediaSettings} onView={viewEvents} onStream={viewEvents} onEditMedia={editMedia} onEdit={beginEdit} onToggle={toggle} onAutomation={toggleAutomation} onRemove={remove} onMediaChange={setMediaSettings} onSaveMedia={saveMedia} onCancelMedia={()=>setMediaSettings(null)}/>)}</div>}
    </section>
    <details className="source-manual-setup" ref={manualSetupRef}><summary>{t(editing?'Ubah sumber':'Tambah sumber secara manual')}</summary>{editing&&<p className="source-editing-note">{t('Mengubah sumber')}: <strong>{editing.name}</strong></p>}<form className="source-form" onSubmit={submit}><label>{t('Nama sumber')}<input ref={nameInputRef} value={name} required maxLength={100} onChange={e=>setName(e.target.value)} placeholder={t('Contoh: Sensor gudang')}/></label><label>{t('Jenis')}<select value={kind} onChange={e=>setKind(e.target.value)}><option value="iot">{t('IoT / sensor')}</option><option value="camera">{t('Kamera')}</option><option value="service">{t('Layanan lain')}</option></select></label><label>{t('Interval data harapan (detik)')}<input type="number" min="10" max="86400" required value={expectedInterval} onChange={e=>setExpectedInterval(e.target.value)}/></label><button className="primary" disabled={submitting}>{t(submitting?'Menyimpan…':editing?'Simpan perubahan':'Tambah sumber')}</button>{editing && <button type="button" className="secondary" onClick={cancelSourceEdit}>{t('Batal')}</button>}</form></details>
    {credential && <div className="credential"><strong>{t('Sumber dibuat')}</strong><p>{t('Salin token sekarang; token tidak akan ditampilkan lagi. Gunakan koneksi HTTPS saat mengirim data melalui jaringan.')}</p><label>{t('Alamat penerima')}<input readOnly value={window.location.origin+credential.ingest_path} onFocus={e=>e.target.select()}/></label><label>{t('Token')}<input readOnly value={credential.token} onFocus={e=>e.target.select()}/></label><p>{t('Alamat localhost hanya dapat diakses dari mesin ini. Perangkat lain memerlukan gateway yang aman.')}</p><button className="secondary" onClick={()=>setCredential(null)}>{t('Saya sudah menyimpan token')}</button></div>}

    {selectedSource && <SourceDetailsDialog source={selectedSource} events={events} loading={eventsLoading} error={eventsError} requestMessage={requestMessage} requestState={requestState} previewUrl={previewUrl} previewStatus={previewStatus} onRequestData={requestSourceData} mode={dialogMode} onRefresh={()=>refreshSourceDetails(selectedSource)} onClose={closeEvents}/>}
    </></div>}
  </div>;
}

export default function App() {
  const [language, setLanguage] = useState(() => localStorage.getItem('kanca-language') === 'id' ? 'id' : 'en');
  const t = text => language === 'en' ? englishTranslations.get(text) || text : text;
  const dateLocale = language === 'en' ? 'en-US' : 'id-ID';
  const [connected, setConnected] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [instruction, setInstruction] = useState('');
  const [chats, setChats] = useState([]);
  const [current, setCurrent] = useState(() => sessionStorage.getItem('kanca-conversation'));
  const [messages, setMessages] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notice, setNotice] = useState('');
  const [externalSources, setExternalSources] = useState([]);
  const [view, setView] = useState('dashboard');
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const notificationTrigger = useRef(null);
  const [theme, toggleTheme] = useTheme();
  const [pendingChat, setPendingChat] = useState(null);
  const [confirmation, setConfirmation] = useState(null);
  const currentRef = useRef(current);
  const refreshInFlight = useRef(null);
  const refreshAgain = useRef(false);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const rerunPending = useRef(false);
  const promptOptions = language==='en' ? [
    {icon:'thermometer',label:'Check room temperature',prompt:'Check the room temperature sensor.'},
    {icon:'list',label:'Review order discrepancies',prompt:'Check the orders and look for quantity discrepancies.'},
    {icon:'clock',label:'Monitor unpacked orders',prompt:'Check which orders have not been packed.'}
  ] : [
    {icon:'thermometer',label:'Periksa suhu ruangan',prompt:'Periksa suhu sensor simulasi.'},
    {icon:'list',label:'Cek selisih pesanan',prompt:'Periksa pesanan dan lihat apakah ada selisih jumlah.'},
    {icon:'clock',label:'Pantau pesanan belum dikemas',prompt:'Periksa pesanan yang belum dikemas.'}
  ];

  useEffect(()=>{document.documentElement.lang=language;localStorage.setItem('kanca-language',language);},[language]);

  const selectChat = useCallback(id => { currentRef.current = id; setCurrent(id); if (id) sessionStorage.setItem('kanca-conversation', id); else sessionStorage.removeItem('kanca-conversation'); }, []);
  const refresh = useCallback(() => {
    if (refreshInFlight.current) {
      refreshAgain.current = true;
      return refreshInFlight.current;
    }
    const run = async () => {
      do {
        refreshAgain.current = false;
        const [conversations, allTasks, external, notices, unread] = await Promise.all([api('/v1/conversations'), api('/v1/tasks'), api('/v1/sources'), api('/v1/notifications'), api('/v1/notifications/unread-count')]);
        let selected = currentRef.current;
        if (selected && !conversations.some(chat => chat.id === selected)) { selected = null; selectChat(null); }
        if (!selected && conversations.length) { selected = conversations[0].id; selectChat(selected); }
        const fresh = selected ? await api(`/v1/conversations/${encodeURIComponent(selected)}/messages`) : [];
        if (selected !== currentRef.current) { refreshAgain.current = true; continue; }
        setChats(conversations); setMessages(fresh); setTasks(allTasks); setExternalSources(external); setNotifications(notices); setUnreadCount(unread.count); setConnected(true);
      } while (refreshAgain.current);
    };
    setRefreshing(true);
    const request = run().finally(() => { if (refreshInFlight.current === request) { refreshInFlight.current = null; setRefreshing(false); } });
    refreshInFlight.current = request;
    return request;
  }, [selectChat]);

  useEffect(() => {
    let active = true;
    const sync = async () => {
      if (document.visibilityState === 'hidden') return;
      try { await refresh(); }
      catch (error) { if(active) { setConnected(false); setFeedback(error.message); } }
      finally { if(active) setInitialLoading(false); }
    };
    api('/v1/session').then(sync).catch(error => { if(active) { setFeedback(error.message); setInitialLoading(false); } });
    const onVisible = () => { if(document.visibilityState === 'visible') sync(); };
    window.addEventListener('focus', onVisible);
    document.addEventListener('visibilitychange', onVisible);
    return () => { active = false; window.removeEventListener('focus', onVisible); document.removeEventListener('visibilitychange', onVisible); };
  }, [refresh]);

  useEffect(() => { document.querySelectorAll('.main .scroll').forEach(el => { el.scrollTop = 0; }); }, [view]);
  useEffect(() => {
    if (!notificationsOpen) return;
    const drawer = document.querySelector('.notification-drawer');
    const focusable = () => [...drawer.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')].filter(element => !element.hidden && element.getAttribute('aria-hidden') !== 'true');
    const closeOnKey = event => {
      if (event.key === 'Escape') { event.preventDefault(); setNotificationsOpen(false); return; }
      if (event.key !== 'Tab') return;
      const items = focusable();
      if (!items.length) { event.preventDefault(); drawer.focus(); return; }
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && (document.activeElement === first || !drawer.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || !drawer.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
    };
    const background = [...document.querySelectorAll('.app > :not(.notification-overlay)')];
    const previousInert = background.map(element => element.inert);
    background.forEach(element => { element.inert = true; });
    drawer.addEventListener('keydown', closeOnKey);
    return () => {
      drawer.removeEventListener('keydown', closeOnKey);
      background.forEach((element, index) => { element.inert = previousInert[index]; });
      notificationTrigger.current?.focus();
    };
  }, [notificationsOpen]);

  async function newChat() {
    try { const chat = await api('/v1/conversations', {method:'POST', body:JSON.stringify({})}); selectChat(chat.id); setView('chat'); setMessages([]); setInstruction(''); await refresh(); inputRef.current?.focus(); }
    catch(error) { setFeedback(error.message); }
  }
  async function select(id) { selectChat(id); setView('chat'); setMessages([]); try { await refresh(); } catch(error) { setFeedback(error.message); } }
  async function action(task, actionName, body) { try { setFeedback(''); await api(`/v1/tasks/${encodeURIComponent(task.id)}/${actionName}`, {method:'POST', body:body ? JSON.stringify(body) : undefined}); await refresh(); } catch(error) { setFeedback(error.message); } }
  async function rerun(task) { if(rerunPending.current)return; rerunPending.current=true; try { setFeedback(''); setNotice(''); await api(`/v1/tasks/${encodeURIComponent(task.id)}/rerun`,{method:'POST'}); await refresh(); setView('workers'); setNotice(t('Rencana baru sudah dibuat. Periksa dan setujui untuk menjalankannya.')); } catch(error) { setFeedback(error.message); } finally { rerunPending.current=false; } }
  async function markRead(item) { try { await api(`/v1/notifications/${encodeURIComponent(item.id)}/read`,{method:'POST'}); await refresh(); } catch(error) { setFeedback(error.message); } }
  async function markAllRead() { try { await api('/v1/notifications/read-all',{method:'POST'}); await refresh(); } catch(error) { setFeedback(error.message); } }
  async function edit(task, interval, runs) { try { setFeedback(''); await api(`/v1/tasks/${encodeURIComponent(task.id)}/schedule`, {method:'PATCH', body:JSON.stringify({version:task.version,schedule:{interval_seconds:interval,max_runs:runs}})}); await refresh(); return true; } catch(error) { setFeedback(error.message); return false; } }
  function archive(task) { setConfirmation({title:t('Hapus tugas dari daftar?'),description:t('Tugas yang aktif akan dihentikan. Riwayatnya tetap disimpan.'),onConfirm:async()=>{try { setFeedback(''); await api(`/v1/tasks/${encodeURIComponent(task.id)}`,{method:'DELETE'}); await refresh(); } catch(error) { setFeedback(error.message); }}}); }
  async function moveChat(chat) {try{await api(`/v1/conversations/${encodeURIComponent(chat.id)}`,{method:'PATCH',body:JSON.stringify({status:chat.status==='draft'?'active':'draft'})});await refresh();}catch(error){setFeedback(error.message);}}
  function deleteChat(chat) {setConfirmation({title:t('Hapus percakapan?'),description:t('Percakapan akan dihapus dari daftar. Tugas yang sudah dibuat tetap berjalan dan tersedia di Tugas latar belakang.'),onConfirm:async()=>{try{await api(`/v1/conversations/${encodeURIComponent(chat.id)}`,{method:'DELETE'});if(currentRef.current===chat.id){selectChat(null);setMessages([]);}await refresh();}catch(error){setFeedback(error.message);}}});}
  function clearHistory() {if(!chats.length||busy)return;setConfirmation({title:t('Bersihkan riwayat percakapan?'),description:t('Semua percakapan akan dihapus dari daftar riwayat. Tugas yang sudah dibuat tetap berjalan dan tersedia di Tugas latar belakang.'),onConfirm:async()=>{try{setFeedback('');await api('/v1/conversations',{method:'DELETE'});selectChat(null);setMessages([]);setInstruction('');setPendingChat(null);await refresh();}catch(error){setFeedback(error.message);}}});}
  async function send(event) {
    event?.preventDefault(); const text = instruction.trim();
    if (!connected || !text || busy) return;
    const optimisticId = `optimistic-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const optimisticMessage = {id:optimisticId,role:'user',content:text,created_at:new Date().toISOString()};
    setBusy(true); setFeedback(''); setMessages(previous=>[...previous,optimisticMessage]);
    setPendingChat(currentRef.current || '__new__');
    requestAnimationFrame(()=>scrollRef.current?.scrollTo({top:scrollRef.current.scrollHeight,behavior:'smooth'}));
    try {
      let target = currentRef.current;
      if (!target) { const chat = await api('/v1/conversations', {method:'POST', body:JSON.stringify({})}); target = chat.id; selectChat(target); }
      setPendingChat(target);
      setInstruction('');
      await api(`/v1/conversations/${encodeURIComponent(target)}/messages`, {method:'POST', body:JSON.stringify({content:text})});
      setFeedback(''); await refresh();
      if (target === currentRef.current) scrollRef.current?.scrollTo({top:scrollRef.current.scrollHeight, behavior:'smooth'});
    } catch(error) { setMessages(previous=>previous.filter(item=>item.id!==optimisticId)); setFeedback(error.message); setInstruction(text); } finally { setBusy(false); setPendingChat(null); }
  }

  return <LanguageContext.Provider value={{language,t,dateLocale,setLanguage}}><div className={`app ${['dashboard','chat'].includes(view)?'has-iot-sidebar':''}`}><aside className="sidebar">
    <Brand/>
    <div className="sidebar-content">
    <section className="sidebar-nav"><p className="side-label">{t('Menu utama')}</p><button className="side-button nav-row" aria-current={view==='dashboard'?'page':undefined} onClick={()=>setView('dashboard')}><span className="nav-icon"><Icon name="dashboard"/></span><span className="nav-label">{t('Dashboard')}</span></button><button className="side-button nav-row" aria-current={view==='workers'?'page':undefined} onClick={()=>setView('workers')}><span className="nav-icon"><Icon name="clock"/></span><span className="nav-label">{t('Daftar tugas')}</span><span className="task-count" aria-label={`${tasks.filter(t=>t.status==='scheduled'||t.status==='running').length} ${t('tugas aktif')}`}>{tasks.filter(t=>t.status==='scheduled'||t.status==='running').length}</span></button><button className="side-button nav-row" aria-current={view==='sources'?'page':undefined} onClick={()=>setView('sources')}><span className="nav-icon"><Icon name="plug"/></span><span className="nav-label">{t('Integrasi')}</span></button></section>
    <section className="history-section"><p className="side-label">{t('Riwayat percakapan')}</p>{!chats.length && <p className="meta">{t('Belum ada percakapan')}</p>}{['active','draft'].map(status=>{const group=chats.filter(chat=>chat.status===status);return (group.length>0 || status==='active') && <div className="history-group" key={status}><div className="history-group-heading"><p className="history-label">{t(status==='draft'?'Draft':'Percakapan')}</p>{status==='active' && <div className="history-heading-actions">{chats.length>0&&<button className="history-clear" type="button" onClick={clearHistory} disabled={!connected||busy} aria-label={t('Bersihkan riwayat')} title={t('Bersihkan riwayat')}><Icon name="trash" size={15}/></button>}<button className="history-new-chat" type="button" onClick={newChat} disabled={!connected} aria-label={t('Chat baru')} title={t('Chat baru')}><Icon name="plus" size={16}/></button></div>}</div>{group.map(chat=><div className={`chat-row ${chat.id===current && (view==='chat'||view==='dashboard')?'selected':''}`} key={chat.id}><button className="chat-select" aria-current={chat.id===current && (view==='chat'||view==='dashboard')?'page':undefined} onClick={()=>select(chat.id)} title={chat.title}>{chat.title}</button><details className="chat-menu"><summary aria-label={t('Opsi untuk {title}').replace('{title}',chat.title)}><Icon name="dots" size={16}/></summary><div className="chat-menu-items"><button onClick={e=>{e.currentTarget.closest('details').open=false;moveChat(chat);}}>{t(status==='draft'?'Kembalikan':'Pindah ke draft')}</button><button className="menu-danger" onClick={e=>{e.currentTarget.closest('details').open=false;deleteChat(chat);}}>{t('Hapus')}</button></div></details></div>)}</div>})}</section>
    <div className="side-note"><a href="/docs" target="_blank" rel="noreferrer">{t('Dokumentasi API ↗')}</a></div>
    </div>
    </aside><main className="main"><header className="topbar"><Brand className="brand brand-topbar"/><div className="topbar-title"><strong>{t(view==='dashboard'?'Dashboard':view==='workers'?'Tugas latar belakang':view==='notifications'?'Notifikasi':view==='sources'?'Sumber eksternal':'Ruang percakapan')}</strong><p>{t(view==='dashboard'?'Pantau perangkat dan lanjutkan percakapan':view==='workers'?'Kelola pemantauanmu di satu tempat':view==='notifications'?'Pembaruan tugasmu':view==='sources'?'Kelola perangkat dan layanan':'Tempat untuk mendelegasikan tugasmu')}</p></div><div className="topbar-actions">{(view==='chat'||view==='dashboard') && <ChatTopics chats={chats} current={current} onSelect={select} onNew={newChat}/>}<span className={`badge ${refreshing?'is-refreshing':''}`} aria-live="polite">{refreshing&&<span className="loading-spinner" aria-hidden="true"/>}{t(refreshing?'Memperbarui…':connected?'Terhubung':'Belum terhubung')}</span><button className="icon-button theme-toggle" type="button" onClick={toggleTheme} aria-label={t(theme==='dark'?'Aktifkan mode terang':'Aktifkan mode gelap')} title={t(theme==='dark'?'Mode terang':'Mode gelap')}><Icon name={theme==='dark'?'sun':'moon'}/></button><button className="language-toggle" type="button" onClick={()=>setLanguage(language==='id'?'en':'id')} aria-label={t(language==='id'?'Beralih ke bahasa Inggris':'Beralih ke bahasa Indonesia')} title={t(language==='id'?'Beralih ke bahasa Inggris':'Beralih ke bahasa Indonesia')}>{language==='id'?'EN':'ID'}</button><button className="notification-button" onClick={event=>{notificationTrigger.current=event.currentTarget;setNotificationsOpen(true);}} aria-label={`${t('Notifikasi')}, ${unreadCount} ${t('belum dibaca')}`} aria-current={notificationsOpen?'page':undefined} title={t('Notifikasi')}><Icon name="bell"/>{unreadCount>0 && <span className="notification-count" aria-hidden="true">{unreadCount>99?'99+':unreadCount}</span>}</button></div></header>
    {initialLoading ? <div className="app-initial-loading" role="status"><span className="loading-spinner" aria-hidden="true"/>{t('Memuat data aplikasi…')}</div> : view==='workers' ? <div className="scroll"><Workers tasks={tasks} onAction={action} onEdit={edit} onArchive={archive} onCreate={newChat} onRerun={rerun}/><div className="workers-error" role="status">{notice}</div><div className="workers-error error" role="alert">{feedback}</div></div> : view==='sources' ? <div className="scroll"><Sources sources={externalSources} onChanged={refresh} requestConfirm={setConfirmation}/></div> : <>
    <div className="scroll" ref={scrollRef}><div className="chat-workspace"><div className="content"><div className="welcome"><div className="eyebrow">{t(view==='dashboard'?'RUANG KENDALI':'Selamat datang di Kanca ✳')}</div><h1>{t(view==='dashboard'?'Pantau aktivitas. Jaga semuanya bergerak.':'What would you like to keep an eye on?')}</h1><p>{t(view==='dashboard'?'Perangkat, pemeriksaan, dan aktivitas Kanca dalam satu ruang kendali. Mulai pemeriksaan dari instruksi di bawah.':'Beritahu apa yang ingin kamu pantau. Pemeriksaan dan tindakan aman langsung berjalan; tindakan berisiko menunggu persetujuanmu.')}</p></div>
      <div className="separator"/>
      <div className="message-list" aria-live="polite">{!messages.length && !busy && <p className="meta">{t('Belum ada aktivitas di percakapan ini. Mulai pemeriksaan dari instruksi di bawah.')}</p>}{messages.map(item => <div className={`message ${item.role==='user'?'user-message':'assistant-message'}`} key={item.id}><div className={`avatar ${item.role === 'user' ? 'user' : ''}`}>{item.role === 'user' ? (language==='id'?'K':'Y') : 'k.'}</div><div className="message-body"><div className="message-head">{t(item.role === 'user' ? 'Kamu' : 'Kanca')} <time dateTime={item.created_at} title={new Date(item.created_at).toLocaleString(dateLocale)}>{formatRelativeTime(item.created_at,dateLocale)}</time></div><div className="bubble">{item.role === 'assistant' ? <ChatReply content={item.content}/> : item.content}</div>{item.task && <TaskCard task={item.task} onAction={action} onRerun={rerun}/>}</div></div>)}{busy && (pendingChat===current || (!current&&pendingChat==='__new__')) && <div className="message assistant-message" role="status" aria-label={t('Kanca sedang mengetik')}><div className="avatar">k.</div><div className="message-body"><div className="message-head">Kanca</div><div className="typing"><span/><span/><span/></div></div></div>}</div><div className="error" role="alert">{feedback}</div>
    </div><aside className="iot-inline"><IoTPanel/></aside></div></div><div className="composer-wrap"><div className="suggestions" aria-label={t('Instruksi cepat')}>{promptOptions.map(({icon,label,prompt}) => <button type="button" key={label} onClick={() => {setInstruction(prompt);inputRef.current?.focus();}}><Icon name={icon} size={17}/>{t(label)}</button>)}</div><form className="composer" onSubmit={send}><textarea ref={inputRef} value={instruction} onChange={e=>setInstruction(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();send();}}} placeholder={t('Ceritakan apa yang ingin kamu lakukan...')} aria-label={t('Instruksi untuk Kanca')} maxLength={4000}/><div className="composer-bottom"><span>{t('Enter untuk kirim · Shift + Enter untuk baris baru')}</span><button className="send" aria-label={t('Kirim instruksi')} disabled={!connected || busy}><Icon name="up"/></button></div></form><p className="footer">{t('Kanca dapat membuat kesalahan. Periksa rencana sebelum menyetujui.')}</p></div>
  </>}</main>{(view==='dashboard'||view==='chat') && <aside className="iot-sidebar" aria-label={t('Perangkat IoT')}><IoTPanel/></aside>}<nav className="mobile-bottom-nav" aria-label={t('Navigasi utama')}>{[['dashboard','Dashboard'],['chat','Chat'],['workers','Tugas'],['sources','Integrasi']].map(([tab,label]) => <button key={tab} className="tab-button" onClick={()=>setView(tab)} aria-current={view===tab?'page':undefined}><Icon name={{dashboard:'dashboard',chat:'chat',workers:'clock',sources:'plug'}[tab]}/><span className="nav-label">{t(label)}</span>{tab==='workers'&&tasks.some(t=>t.status==='scheduled'||t.status==='running') && <span className="tab-dot" aria-hidden="true"/>}</button>)}</nav>{notificationsOpen && <div className="notification-overlay" role="presentation" onMouseDown={event=>{if(event.target===event.currentTarget)setNotificationsOpen(false);}}><aside className="notification-drawer" role="dialog" aria-modal="true" aria-label={t('Notifikasi')}><Notifications items={notifications} onRead={markRead} onReadAll={markAllRead} unreadCount={unreadCount} onRerun={rerun} onClose={()=>setNotificationsOpen(false)} onChanged={refresh}/><div className="workers-error error" role="alert">{feedback}</div></aside></div>}{confirmation && <ConfirmDialog config={confirmation} onClose={()=>setConfirmation(null)}/>}</div></LanguageContext.Provider>;
}
