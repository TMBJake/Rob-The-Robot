from datetime import datetime

from flask import Flask, render_template, jsonify, request
import sqlite3
import requests
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
load_dotenv(".env.local")


ADAFRUIT_IO_USERNAME = os.getenv("ADAFRUIT_IO_USERNAME")
ADAFRUIT_IO_KEY = os.getenv("ADAFRUIT_IO_KEY")
AIO_BASE_URL = f"https://io.adafruit.com/api/v2/{ADAFRUIT_IO_USERNAME}"

app = Flask(__name__)


def get_neon_connection():
    return psycopg2.connect(
        dbname=os.getenv("NEON_DBNAME"),                 # or your DB name
        user=os.getenv("NEON_USER"),             # your Neon role
        password=os.getenv("NEON_PASSWORD"),   # DON'T commit this
        host=os.getenv("NEON_HOST"),
        port=os.getenv("NEON_PORT"),
        sslmode=os.getenv("NEON_SSLMODE"),
        cursor_factory=RealDictCursor,
    )


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/about2')
def about_2():
    return render_template('about2.html')

@app.route('/infrared')
def infrared():
    return render_template('infrared.html')

@app.route('/api/history')
def api_history():
    """
    Returns JSON for a date range:
    GET /api/history?start=YYYY-MM-DD&end=YYYY-MM-DD
    """
    start = request.args.get('start')
    end = request.args.get('end')

    if not start or not end:
        return jsonify({"error": "start and end query parameters are required"}), 400

    # Basic validation
    try:
        datetime.strptime(start, "%Y-%m-%d")
        datetime.strptime(end, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Dates must be in YYYY-MM-DD format"}), 400

    conn = get_neon_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT timestamp, distance, line_side, voltage
        FROM sensor_data
        WHERE timestamp::date BETWEEN %s AND %s
        ORDER BY timestamp;
    """, (start, end))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    labels = []
    distance_vals = []
    voltage_vals = []
    line_side_vals = []

    def encode_line_side(ls):
        if ls == "left":
            return 1
        elif ls == "middle":
            return 2
        elif ls == "right":
            return 3
        elif ls == "stop":
            return 4
        else:
            return 0   # 'none' or unknown

    # Because you're using RealDictCursor, rows are dicts:
    # {'timestamp': ..., 'distance': ..., 'line_side': ..., 'voltage': ...}
    for row in rows:
        ts = row["timestamp"]
        distance = row["distance"]
        line_side = row["line_side"]
        voltage = row["voltage"]

        # ts might already be a string or a datetime, handle both safely
        if isinstance(ts, str):
            labels.append(ts)
        else:
            labels.append(ts.isoformat())

        distance_vals.append(float(distance) if distance is not None else None)
        voltage_vals.append(float(voltage) if voltage is not None else None)
        line_side_vals.append(encode_line_side(line_side))

    return jsonify({
        "labels": labels,
        "distance": distance_vals,
        "voltage": voltage_vals,
        "line_side_values": line_side_vals,
    })


def send_car_control_command(value: str) -> bool:
    url = f"{AIO_BASE_URL}/feeds/car-control/data"
    headers = {
        "X-AIO-Key": ADAFRUIT_IO_KEY,
        "Content-Type": "application/json",
    }
    payload = {"value": value}

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=5)
        r.raise_for_status()
        print(f"Sent car-control='{value}' to Adafruit IO")
        return True
    except Exception as e:
        print(f"Error sending car-control command: {e}")
        return False



def send_car_mode_command(value: str) -> bool:
    url = f"{AIO_BASE_URL}/feeds/car-mode/data"
    headers = {
        "X-AIO-Key": ADAFRUIT_IO_KEY,
        "Content-Type": "application/json",
    }
    payload = {"value": value}

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=5)
        r.raise_for_status()
        print(f"Sent car-mode='{value}' to Adafruit IO")
        return True
    except Exception as e:
        print(f"Error sending car-mode command: {e}")
        return False



#This is where the code checks what command to send regarding infrared
@app.route('/api/infrared/start', methods=['POST'])
def api_infrared_start():
    success = send_car_mode_command("infrared")
    status = "ok" if success else "error"
    return jsonify({"status": status, "mode": "infrared"}), (200 if success else 500)

@app.route('/api/ultrasonic/start', methods=['POST'])
def api_ultrasonic_start():
    success = send_car_mode_command("ultrasonic")
    status = "ok" if success else "error"
    return jsonify({"status": status, "mode": "ultrasonic"}), (200 if success else 500)


"""
--------------------------------------
|This is for the directional commands|
--------------------------------------
"""
@app.route('/movement')
def movement():
    return render_template('movement.html')

@app.route('/history')
def history():
    return render_template('history.html')

@app.route('/api/infrared/stop', methods=['POST'])
def api_infrared_stop():
    success = send_car_mode_command("stop")
    status = "ok" if success else "error"
    return jsonify({"status": status, "mode": "stop"}), (200 if success else 500)

@app.route('/api/move/forward', methods=['POST'])
def api_move_forward():
    success = send_car_control_command("forward")
    return jsonify({"status": "ok" if success else "error", "command": "forward"}), (200 if success else 500)

@app.route('/api/move/backward', methods=['POST'])
def api_move_backward():
    success = send_car_control_command("backward")
    return jsonify({"status": "ok" if success else "error", "command": "backward"}), (200 if success else 500)

@app.route('/api/move/left', methods=['POST'])
def api_move_left():
    success = send_car_control_command("left")
    return jsonify({"status": "ok" if success else "error", "command": "left"}), (200 if success else 500)

@app.route('/api/move/right', methods=['POST'])
def api_move_right():
    success = send_car_control_command("right")
    return jsonify({"status": "ok" if success else "error", "command": "right"}), (200 if success else 500)

@app.route('/api/move/stop', methods=['POST'])
def api_move_stop():
    success = send_car_control_command("stop")
    return jsonify({"status": "ok" if success else "error", "command": "stop"}), (200 if success else 500)



@app.route('/api/buzzer/toggle', methods=['POST'])
def api_buzzer_toggle():
    """
    Toggle the buzzer on the car (handled as a toggle in MainCode.py).
    Sends 'buzzer-toggle' on the car-control feed.
    """
    success = send_car_control_command("buzzer-toggle")
    return jsonify({
        "status": "ok" if success else "error",
        "command": "buzzer-toggle"
    }), (200 if success else 500)


@app.route('/api/camera/<direction>', methods=['POST'])
def api_camera_direction(direction):
    """
    Move the camera in a given direction.
    Valid directions: left, right, up, down, center
    Maps to: cam-left, cam-right, cam-up, cam-down, cam-center
    """
    mapping = {
        "left": "cam-left",
        "right": "cam-right",
        "up": "cam-up",
        "down": "cam-down",
        "center": "cam-center",
    }

    if direction not in mapping:
        return jsonify({"status": "error", "error": "invalid direction"}), 400

    cmd_value = mapping[direction]
    success = send_car_control_command(cmd_value)

    return jsonify({
        "status": "ok" if success else "error",
        "command": cmd_value
    }), (200 if success else 500)


@app.route('/api/robot-controls')
def robot_controls():
    return render_template('robot_controls.html')

if __name__ == '__main__':
    app.run(debug=True)