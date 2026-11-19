import json
import time
import threading
import colorsys
import websocket
import tinytuya

# ============================================================
# CONFIGURATION
# ============================================================

BEAT_SABER_WS = "ws://127.0.0.1:6557/socket"

# Put your actual credentials here.
# Prefer environment variables or a separate config file.
BULBS = [
    {
        "name": "Left bulb",
        "id": "bulb id here",
        "ip": "bulb ip here",
        "key": "bulb key here"
    },
    {
        "name": "Right bulb",
        "id": "bulb id here",
        "ip": "bulb ip here",
        "key": "bulb key here"
    }
]

BASE_BRIGHTNESS = 255

# HueSaber default event colors
LEFT_COLOR = (200, 20, 20)
RIGHT_COLOR = (20, 20, 200)
BOOST_LEFT = LEFT_COLOR
BOOST_RIGHT = RIGHT_COLOR
OBSTACLE_COLOR = (200, 20, 20)

# Event configuration
EVENTS = {
    "noteCut": True,
    "noteMissed": True,
    "bombCut": True,
    "obstacle": True,
    "failed": True,
    "beatmap": True,
}

# Beat Saber lighting event types
MAP_EVENT_TYPES = {
    0: "back_lasers",
    1: "ring_lights",
    2: "left_lasers",
    3: "right_lasers",
    4: "center_lights",
    6: "custom_1",
    7: "custom_2",
    10: "custom_3",
    11: "custom_4",
}

# ============================================================
# TUYA INITIALIZATION
# ============================================================

devices = []
device_lock = threading.Lock()
timers = []
timers_lock = threading.Lock()

def connect_bulbs():
    for bulb in BULBS:
        print("Connecting to", bulb["name"])

        device = tinytuya.BulbDevice(
            bulb["id"],
            bulb["ip"],
            bulb["key"],
            version=3.3
        )

        device.set_socketPersistent(True)
        device.set_sendWait(None)
        device.set_retry(False)

        devices.append(device)

    for device in devices:
        device.set_mode("music")

    print("Both bulbs connected!")

# ============================================================
# COLOR FUNCTIONS
# ============================================================

def clamp(value):
    return max(0, min(255, int(value)))


def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(
        int(value[i:i+2], 16)
        for i in (0, 2, 4)
    )


def send_color(device, color):
    r, g, b = [clamp(x) for x in color]

    try:
        with device_lock:
            device.set_music_colour(
                tinytuya.BulbDevice.MUSIC_TRANSITION_JUMP,
                r, g, b,
                nowait=True
            )
    except Exception as error:
        print("Tuya error:", error)


def set_both(color):
    for device in devices:
        send_color(device, color)


def set_left(color):
    send_color(devices[0], color)


def set_right(color):
    send_color(devices[1], color)


def set_brightness(color, factor):
    return tuple(clamp(c * factor) for c in color)

# ============================================================
# TIMED LIGHT EFFECTS
# ============================================================

def schedule(callback, delay):
    timer = threading.Timer(delay, callback)
    timer.daemon = True

    with timers_lock:
        timers.append(timer)

    timer.start()


def flash(device, color, duration=0.3):
    send_color(device, set_brightness(color, 1.25))

    schedule(
        lambda: send_color(device, color),
        duration
    )


def fade(device, color, duration=0.6):
    steps = 8

    for i in range(steps):
        factor = 1.0 - (i + 1) / steps

        schedule(
            lambda f=factor: send_color(
                device,
                set_brightness(color, f)
            ),
            duration * (i + 1) / steps
        )

    schedule(
        lambda: send_color(device, (0, 0, 0)),
        duration + 0.02
    )


def temporary_color(device, color, duration):
    send_color(device, color)

    schedule(
        lambda: send_color(device, (0, 0, 0)),
        duration
    )

# ============================================================
# BEATMAP LIGHTING EVENTS
# ============================================================

def map_event(event_data):
    global LEFT_COLOR, RIGHT_COLOR
    global BOOST_LEFT, BOOST_RIGHT

    if not EVENTS["beatmap"]:
        return

    event = event_data.get("beatmapEvent")

    if not event:
        return

    if "boostColorsAreOn" in event:
        if event["boostColorsAreOn"]:
            left = BOOST_LEFT
            right = BOOST_RIGHT
        else:
            left = LEFT_COLOR
            right = RIGHT_COLOR
    else:
        left = LEFT_COLOR
        right = RIGHT_COLOR

    value = event.get("value", 0)

    next_event = event_data.get(
        "nextSameTypeEventData", {}
    )

    event_time = event_data.get("time", 0)
    next_time = next_event.get("time", event_time + 0.3)

    duration = max(
        0.15,
        min(0.5, next_time - event_time)
    )

    event_type = event.get("type")

    if event_type not in MAP_EVENT_TYPES:
        return

    # HueSaber maps event types 2 and 3
    # to left and right laser groups.
    if event_type == 2:
        targets = [(devices[0], left)]
    elif event_type == 3:
        targets = [(devices[1], right)]
    else:
        targets = [
            (devices[0], left),
            (devices[1], right)
        ]

    for device, color in targets:

        if value == 0:
            send_color(device, (0, 0, 0))

        elif value == 1:
            send_color(device, color)

        elif value == 2:
            flash(device, color, max(0.15, min(duration, 0.5)))

        elif value == 3:
            fade(device, color, max(0.15, min(duration, 0.6)))

        elif value == 5:
            send_color(device, color)

        elif value == 6:
            flash(device, color, max(0.15, min(duration, 0.5)))

        elif value == 7:
            fade(device, color, max(0.15, min(duration, 0.6)))

# ============================================================
# GAME EVENT HANDLER
# ============================================================

in_wall = False


def handle_event(data):
    global in_wall
    global LEFT_COLOR, RIGHT_COLOR
    global BOOST_LEFT, BOOST_RIGHT

    event = data.get("event")

    # Ignore irrelevant events while inside walls,
    # matching HueSaber's behavior.
    if in_wall and event not in (
        "obstacleExit", "failed", "menu"
    ):
        return

    # ---------------- BEATMAP EVENTS ----------------

    if event == "beatmapEvent":
        map_event(data)

    # ---------------- NOTE CUT ----------------

    elif event == "noteCut" and EVENTS["noteCut"]:

        for device in devices:
            flash(device, (255, 255, 255), 0.3)

    # ---------------- NOTE MISSED ----------------

    elif event == "noteMissed" and EVENTS["noteMissed"]:

        for device, color in zip(
            devices,
            [LEFT_COLOR, RIGHT_COLOR]
        ):
            temporary_color(device, color, 1.0)

    # ---------------- BOMB HIT ----------------

    elif event == "bombCut" and EVENTS["bombCut"]:

        for device, color in zip(
            devices,
            [LEFT_COLOR, RIGHT_COLOR]
        ):
            temporary_color(device, color, 0.6)

    # ---------------- WALL ENTER ----------------

    elif event == "obstacleEnter" and EVENTS["obstacle"]:

        in_wall = True

        for device in devices:
            send_color(device, OBSTACLE_COLOR)

    # ---------------- WALL EXIT ----------------

    elif event == "obstacleExit":

        in_wall = False

        set_both((0, 0, 0))

    # ---------------- SONG FAILED ----------------

    elif event == "failed" and EVENTS["failed"]:

        in_wall = False

        set_both((255, 0, 0))

        schedule(
            lambda: set_both((0, 0, 0)),
            2.0
        )

    # ---------------- SONG START ----------------

    elif event == "songStart":

        set_both((0, 0, 0))

        status = data.get("status", {})
        beatmap = status.get("beatmap", {})

        colors = beatmap.get("color", {})

        if colors:
            LEFT_COLOR = tuple(
                colors.get("environment0", LEFT_COLOR)
            )

            RIGHT_COLOR = tuple(
                colors.get("environment1", RIGHT_COLOR)
            )

            BOOST_LEFT = tuple(
                colors.get("environment0Boost", LEFT_COLOR)
            )

            BOOST_RIGHT = tuple(
                colors.get("environment1Boost", RIGHT_COLOR)
            )

        print(
            "Song started:",
            beatmap.get("songAuthorName", ""),
            "-",
            beatmap.get("songName", "")
        )

    # ---------------- PAUSE ----------------

    elif event == "pause":
        set_both((0, 127, 255))

    # ---------------- RESUME ----------------

    elif event == "resume":
        pass

    # ---------------- FINISHED ----------------

    elif event == "finished":
        set_both((255, 255, 255))

    # ---------------- MENU ----------------

    elif event == "menu":

        in_wall = False
        set_both((255, 255, 255))

        print("Returned to menu")

# ============================================================
# WEBSOCKET
# ============================================================

def on_message(ws, message):
    try:
        data = json.loads(message)
        handle_event(data)

    except Exception as error:
        print("Event processing error:", error)


def on_error(ws, error):
    print("Beat Saber connection error:", error)


def on_close(ws, code, message):
    print("Beat Saber disconnected")


def on_open(ws):
    print("Connected to Beat Saber!")
    print("Waiting for game events...")

    # Start with lights off
    set_both((0, 0, 0))


# ============================================================
# MAIN
# ============================================================

try:
    connect_bulbs()

    print("Connecting to Beat Saber...")
    print("WebSocket:", BEAT_SABER_WS)

    ws = websocket.WebSocketApp(
        BEAT_SABER_WS,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    ws.run_forever(
        ping_interval=20,
        ping_timeout=10
    )

except KeyboardInterrupt:
    print("\nStopping HueSaber Tuya...")

finally:
    for timer in timers:
        timer.cancel()

    for device in devices:
        try:
            device.close()
        except Exception:
            pass

    print("Connections closed.")
