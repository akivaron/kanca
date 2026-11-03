"""Forward JSON objects from one MQTT topic to a Kanca source."""
import json
import os
import ssl
import httpx
import paho.mqtt.client as mqtt
from common import emit


def main():
    host, topic = os.environ['MQTT_HOST'], os.environ['MQTT_TOPIC']
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if os.getenv('MQTT_USERNAME'):
        client.username_pw_set(os.environ['MQTT_USERNAME'], os.getenv('MQTT_PASSWORD'))
    client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print('MQTT connection rejected', flush=True)
        else:
            client.subscribe(topic, qos=1)
    def on_message(client, userdata, message):
        try:
            if message.retain:
                print('Pesan MQTT retained dilewati karena waktu pengukuran unknown', flush=True)
                return
            payload = json.loads(message.payload)
            if not isinstance(payload, dict):
                raise ValueError('payload must be object')
            emit('mqtt.message', {'topic': message.topic, 'payload': payload})
        except (ValueError, UnicodeDecodeError, httpx.HTTPError):
            print('MQTT message is invalid or could not be forwarded', flush=True)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(host, int(os.getenv('MQTT_PORT', '8883')), 60)
    client.loop_forever(retry_first_connection=True)


if __name__ == '__main__':
    main()
