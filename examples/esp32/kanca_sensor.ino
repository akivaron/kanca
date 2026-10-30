// Contoh ESP32 Arduino: sensor dummy. Gunakan gateway HTTPS dengan sertifikat CA terpercaya.
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>

// Isi melalui konfigurasi perangkat Anda; jangan commit kredensial nyata.
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* KANCA_URL = "https://YOUR_GATEWAY_HOST/v1/ingest/YOUR_SOURCE_ID";
const char* KANCA_TOKEN = "YOUR_SOURCE_TOKEN";
const char* ROOT_CA = R"EOF(
YOUR_ROOT_CA_CERTIFICATE_PEM
)EOF";

void setup() {
  Serial.begin(115200);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClientSecure client;
    client.setCACert(ROOT_CA);
    HTTPClient http;
    if (http.begin(client, KANCA_URL)) {
      http.addHeader("Content-Type", "application/json");
      http.addHeader("Authorization", String("Bearer ") + KANCA_TOKEN);
      int status = http.POST("{\"type\":\"sensor.reading\",\"data\":{\"temperature\":29}}\n");
      Serial.printf("Status pengiriman: %d\n", status);
      http.end();
    }
  }
  delay(30000);
}
