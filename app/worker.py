import time
from app.storage import initialize
from app.service import run_one
from app.webhooks import deliver_one


def main():
    initialize()
    print("Kanca worker started", flush=True)
    while True:
        worked = run_one()
        sent = deliver_one()
        if not worked and not sent:
            time.sleep(1)


if __name__ == "__main__":
    main()
