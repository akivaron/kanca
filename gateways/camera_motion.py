"""Local motion heuristic; sends event metadata only, not video or images."""
import os
import time
import cv2
import httpx
from common import emit


def main():
    source = os.environ['CAMERA_SOURCE']
    capture = cv2.VideoCapture(int(source) if source.isdigit() else source)
    if not capture.isOpened():
        raise SystemExit('Tidak dapat membuka kamera')
    previous, last_sent = None, 0.0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                print('Camera unavailable; stop the gateway and check the source', flush=True)
                break
            gray = cv2.GaussianBlur(cv2.cvtColor(cv2.resize(frame, (320, 180)), cv2.COLOR_BGR2GRAY), (21, 21), 0)
            if previous is not None:
                delta = cv2.absdiff(previous, gray)
                changed = cv2.countNonZero(cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]) / delta.size
                if changed > 0.05 and time.monotonic() - last_sent >= 30:
                    try:
                        emit('camera.motion', {'changed_fraction': round(changed, 3), 'method': 'frame_difference'})
                        last_sent = time.monotonic()
                    except httpx.HTTPError:
                        print('Failed mengirim event kamera', flush=True)
            previous = gray
    finally:
        capture.release()


if __name__ == '__main__':
    main()
