import time
from app.storage import initialize
from app.service import run_one, tick_demo_gateway
from app.webhooks import deliver_one


def main():
    initialize()
    print("Kanca worker started", flush=True)
    while True:
        demo_worked = tick_demo_gateway()
        worked = run_one()
        sent = deliver_one()
        if not demo_worked and not worked and not sent:
            time.sleep(1)


if __name__ == "__main__":
    main()
