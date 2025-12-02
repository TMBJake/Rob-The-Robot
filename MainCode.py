#Add lab 6 parts to this
from car import Car
import argparse
import time
import logging
import os
import paho.mqtt.client as mqtt
import threading
import json
from servo import Servo
from buzzer import Buzzer
from datetime import datetime
import psycopg2
from local_db import init_local_db, insert_local_record, get_unsynced_records, mark_as_synced

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
ENV_FEEDS = {
    "distance": "distance",
    "line_side": "line_side",
    "voltage": "voltage",
    # Dont forget the 3rd one
}
class CarMonitorApp:
    def __init__(self, config_file='config.json'):
            self.config = self.load_config(config_file)
            self.image_dir = 'captured_images'
            self.running = True
            self.mqtt_client = None
            self.mqtt_connected = False
            self.car = Car()
            self.current_mode = "stop"
            init_local_db()
            self.setup_mqtt()
            self.servo = Servo()
            self.buzzer = Buzzer()
            self.camera_pan_angle = 90   
            self.camera_tilt_angle = 90  
            self.camera_step = 10        


    def load_config(self, config_file):
        """Load configuration from JSON file"""
        default_config = {
            "ADAFRUIT_IO_USERNAME": "username",
            "ADAFRUIT_IO_KEY": "userkey",
            "MQTT_BROKER": "io.adafruit.com",
            "MQTT_PORT": 1883,
            "MQTT_KEEPALIVE": 60,
            "camera_enabled": True,
            "capturing_interval": 5,
            "flushing_interval": 10,
            "sync_interval": 300,
            "NEON_DBNAME": "neondb_name",
            "NEON_USER": "neondb_user",
            "NEON_PASSWORD": "password",
            "NEON_HOST": "host_url",
            "NEON_PORT": 5432,
            "NEON_SSLMODE": "require"
        }

        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                return {**default_config, **config}
        except FileNotFoundError:
            logger.warning(f"Config file {config_file} not found, using defaults")
            return default_config


    def setup_mqtt(self):
        """Setup MQTT client for Adafruit IO"""
        try:
            
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.username_pw_set(
                self.config["ADAFRUIT_IO_USERNAME"],
                self.config["ADAFRUIT_IO_KEY"]
                )

            # Set up callbacks
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            self.mqtt_client.on_publish = self.on_mqtt_publish
            self.mqtt_client.on_message = self.on_mqtt_message

            # Connect to broker
            self.mqtt_client.connect(
                self.config["MQTT_BROKER"],
                self.config["MQTT_PORT"],
                self.config["MQTT_KEEPALIVE"]
            )

            # Start the network loop in a separate thread
            self.mqtt_client.loop_start()
            logger.info("MQTT client setup completed")

        except Exception as e:
            logger.error(f"Failed to setup MQTT client: {e}")
            self.mqtt_connected = False
            
            
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback for when MQTT client connects"""
        if rc == 0:
            self.mqtt_connected = True
            logger.info("Connected to MQTT broker")
            
            user = self.config["ADAFRUIT_IO_USERNAME"]
            client.subscribe(f"{user}/feeds/car-mode")
            client.subscribe(f"{user}/feeds/car-control")
            logger.info("Subscribed to the car-mode feed")
        else:
            self.mqtt_connected = False
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")


    def on_mqtt_disconnect(self, client, userdata, rc):
        """Callback for when MQTT client disconnects"""
        self.mqtt_connected = False
        logger.warning("Disconnected from MQTT broker")


    def on_mqtt_publish(self, client, userdata, mid):
        """Callback for when message is published"""
        logger.debug(f"Message {mid} published successfully")
        
        
    def send_to_adafruit_io(self, feed_name, value):
        if not self.mqtt_connected or not self.mqtt_client:
            logger.warning("MQTT client not connected")
            return False

        try:   # send data to Adafruit using MQTT

            topic = f"{self.config['ADAFRUIT_IO_USERNAME']}/feeds/{feed_name}"
            result, mid = self.mqtt_client.publish(topic, str(value))
            if result == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Published {value} to {topic}")
                return True
            else:
                logger.error(f"Failed to publish {value} to {topic}, result={result}")
                return False

        except Exception as e:
            logger.error(f"Error publishing to MQTT: {e}")
            return False
            
            
    def on_mqtt_message(self, client, userdata, msg):
        """Callback for when a subscribed message is received"""
        try:
            value = msg.payload.decode().strip()
            topic = msg.topic
            logger.info(f"MQTT message on {topic}: {value}")

            # If it comes from the car-mode feed, change mode
            if topic.endswith("/car-mode"):
                if value in ("infrared", "ultrasonic", "stop"):
                    self.current_mode = value
                    logger.info(f"Car mode changed to: {self.current_mode}")

                    if value == "stop":
                        # Immediately stop motors when mode is 'stop'
                        if hasattr(self.car, "motor") and self.car.motor:
                            self.car.motor.set_motor_model(0, 0, 0, 0)
          
                    
            elif topic.endswith("/car-control"):
                value = value.lower().strip()
                logger.info(f"car-control command: {value}")

                # Movement commands
                if value in ("forward", "backward", "left", "right", "stop"):
                    motor = self.car.motor
                    if motor is None:
                        logger.warning("No motor detected on car object")
                        return

                    SPEED = -1100

                    if value == "forward":
                        motor.set_motor_model(SPEED, SPEED, SPEED, SPEED)
                    elif value == "backward":
                        motor.set_motor_model(-SPEED, -SPEED, -SPEED, -SPEED)
                    elif value == "left":
                        motor.set_motor_model(-SPEED, -SPEED, SPEED, SPEED)
                    elif value == "right":
                        motor.set_motor_model(SPEED, SPEED, -SPEED, -SPEED)
                    elif value == "stop":
                        motor.set_motor_model(0, 0, 0, 0)

                # NEW: buzzer + camera commands
                elif value == "buzzer-toggle":
                    try:
                        self.buzzer_toggle()
                        logger.info("Toggled buzzer")
                    except Exception as e:
                        logger.error(f"Error toggling buzzer: {e}", exc_info=True)

                elif value == "cam-left":
                    self.camera_left()
                    logger.info("Camera moved left")
                elif value == "cam-right":
                    self.camera_right()
                    logger.info("Camera moved right")
                elif value == "cam-up":
                    self.camera_up()
                    logger.info("Camera moved up")
                elif value == "cam-down":
                    self.camera_down()
                    logger.info("Camera moved down")
                elif value == "cam-center":
                    self.camera_center()
                    logger.info("Camera centered")

                else:
                    logger.warning(f"Unknown car-control command: {value}")
        except Exception as e:
            logger.error(f"Error in on_mqtt_message: {e}", exc_info=True)

    def neon_sync_loop(self):
        """Synchronize unsynced local SQLite records with Neon cloud database."""
        while True:
            try:
                # Try to fetch unsynced records
                rows = get_unsynced_records()

                if not rows:
                    time.sleep(10)
                    continue

                for row in rows:
                    row_id, timestamp, distance, line_side, voltage, synced = row

                    # Send to neon (we implement this next)
                    success = self.send_to_neon(timestamp, distance, line_side, voltage)

                    if success:
                        mark_as_synced(row_id)

            except Exception as e:
                logger.error(f"Error in Neon sync loop: {e}", exc_info=True)

            time.sleep(10)
            
            
    def send_to_neon(self, timestamp, distance, line_side, voltage):
        """Insert one sensor record into the Neon (PostgreSQL) cloud database."""
        cfg = self.config
        try:
            conn = psycopg2.connect(
                dbname=cfg["NEON_DBNAME"],
                user=cfg["NEON_USER"],
                password=cfg["NEON_PASSWORD"],
                host=cfg["NEON_HOST"],
                port=cfg.get("NEON_PORT", 5432),
                sslmode=cfg.get("NEON_SSLMODE", "require"),
            )
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO sensor_data(timestamp, distance, line_side, voltage)
                VALUES (%s, %s, %s, %s)
                """,
                (timestamp, distance, line_side, voltage),
            )
            conn.commit()
            cur.close()
            conn.close()
            logger.info("Synced one record to Neon")
            return True
        except Exception as e:
            logger.error(f"Failed to send to Neon: {e}", exc_info=True)
            return False
            
            
    def send_to_cloud(self, data, feeds):
            success = True
            timestamp = data['timestamp']
            logger.info(f"Processing env. reading from {timestamp}")

            # time.sleep(self.config["capturing_interval"])
            # Send pressure
            if self.send_to_adafruit_io(feeds['distance'], data['distance']):
                logger.info(f"  Distance: {data['distance']} cm")
            else:
                success = False
            if self.send_to_adafruit_io(feeds['line_side'], data['line_side']):
                logger.info(f" Line: {data['line_side']}")
            else:
                success = False
            if self.send_to_adafruit_io(feeds['voltage'], data['voltage']):
                logger.info(f" Voltage: {data['voltage']}V")
            else:
                success = False
            time.sleep(self.config["capturing_interval"])
            return success
            
    
    def data_collection_loop(self, ):
        timestamp = datetime.now().strftime("%Y_%m_%d")
        environmental_data_filename = os.path.abspath(f"{timestamp}_environmental_data.txt")

        logger.info(f"Writing to:\n  {environmental_data_filename}")

        # Append mode + line buffering for faster flush on newline
        with open(environmental_data_filename, "a", buffering=1) as file1:

            last_fsync = time.time()
            while self.running:
                try:
                    # Environmental
                    env_data = self.generate_environmental_data()
                    
                    file1.write(json.dumps(env_data) + "\n")
                    
                    insert_local_record(
                        env_data['timestamp'],
                        env_data['distance'],
                        env_data['line_side'],
                        env_data['voltage']
                    )
                    if self.send_to_cloud(data=env_data, feeds=ENV_FEEDS):
                        logger.info("sent to cloud")
                    else:
                        logger.info("offline, sent env data to local file. will sync later.")
                    logger.info(f"Environmental data: {env_data}")

                    # Ensure data is on-disk regularly (every ~10s)
                    if time.time() - last_fsync > self.config["flushing_interval"]:
                        file1.flush()
                        os.fsync(file1.fileno())
                        last_fsync = time.time()

                    print("sleeping for ", self.config["capturing_interval"])
                    time.sleep(self.config["capturing_interval"])

                except Exception as e:
                    logger.error(f"Error in data collection loop: {e}", exc_info=True)
                    time.sleep(60)



    def generate_environmental_data(self):
        """Collect and send environmental data every 30 seconds"""
        try:
            voltage = None
            if hasattr(self.car, "adc") and self.car.adc and hasattr(self.car.adc, "read_adc"):
                v_pin = float(self.car.adc.read_adc(2))              # volts at ADC pin
                divider = 3 if getattr(self.car.adc, "pcb_version", 1) == 1 else 2
                voltage = round(v_pin * divider, 2)
                distance = None
            if hasattr(self.car, "sonic") and self.car.sonic and hasattr(self.car.sonic, "get_distance"):
                distance = self.car.sonic.get_distance()


            line_side = "none"
            if hasattr(self.car, "infrared") and self.car.infrared:
                infrared_value = self.car.infrared.read_all_infrared()
            if infrared_value == 2:
                line_side = "middle"
            elif infrared_value in (4, 6):
                line_side = "left"
            elif infrared_value in (1, 3):
                line_side = "right"
            elif infrared_value == 7:
                line_side = "stop"
            else:
                line_side = "none"

            print(f"Distance: {distance:.2f} cm")
            print(f"Infrared direction: {line_side}")
            print(f"Battery voltage: {voltage:.2f}")
            data = {
                'timestamp': datetime.now().isoformat(),
                'distance': distance,
                'line_side': line_side,
                'voltage': voltage,
            }
            
            return data
        except Exception as error:
                logger.error(f"Failed to read distance: {error}", exc_info=True)
                # Still return a timestamped payload to avoid KeyError

    def buzzer_on(self):
        if self.buzzer:
            self.buzzer.set_state(True)

    def buzzer_off(self):
        if self.buzzer:
            self.buzzer.set_state(False)

    def buzzer_toggle(self):
        if not self.buzzer:
            return
        # Simple toggle: read current state by tracking it on Car
        if not hasattr(self, "_buzzer_state"):
            self._buzzer_state = False
        self._buzzer_state = not self._buzzer_state
        self.buzzer.set_state(self._buzzer_state)
        
        
    def drive_loop(self):
        """Main driving loop that reacts to current_mode."""
        logger.info("Starting drive loop (listening to car-mode commands)")
        try:
            while self.running:
                if self.current_mode == "infrared":
                    # One "step" of infrared behavior
                    self.car.mode_infrared()
                elif self.current_mode == "ultrasonic":
                    # One "step" of ultrasonic behavior
                    self.car.mode_ultrasonic()
                else:
                    # 'stop' or anything else: just idle
                    time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("Drive loop interrupted by user")
        finally:
            # Stop motors on exit
            if hasattr(self.car, "motor") and self.car.motor:
                self.car.motor.set_motor_model(0, 0, 0, 0)
            logger.info("Drive loop stopped")
            
    '''def run_ultrasonic_mode(self, duration=None):
        print("Starting Ultrasonic mode...")
        start_time = time.time()
        try:
            while True:
                self.car.mode_ultrasonic()
                if duration and (time.time() - start_time) >= duration:
                    break
        except KeyboardInterrupt:
            print("\nUltrasonic mode stopped by user.")
        finally:
            car.close()


    def run_infrared_mode(self, duration=None):
        print("Starting Infrared mode...")
        start_time = time.time()
        try:
            while True:
                self.car.mode_infrared()
                if duration and (time.time() - start_time) >= duration:
                    break
        except KeyboardInterrupt:
            print("\nInfrared mode stopped by user.")
        finally:
            self.car.close()'''
            
            
    def _update_camera_servos(self):
        """Apply current angles to channels '0' (pan) and '1' (tilt)."""
        pan = max(0, min(180, self.camera_pan_angle))
        tilt = max(0, min(180, self.camera_tilt_angle))

        self.camera_pan_angle = pan
        self.camera_tilt_angle = tilt

        # Use your existing Servo API
        self.servo.set_servo_pwm('0', pan)
        self.servo.set_servo_pwm('1', tilt)

    def camera_center(self):
        self.camera_pan_angle = 90
        self.camera_tilt_angle = 90
        self._update_camera_servos()

    def camera_left(self):
        self.camera_pan_angle -= self.camera_step
        self._update_camera_servos()

    def camera_right(self):
        self.camera_pan_angle += self.camera_step
        self._update_camera_servos()

    def camera_up(self):
        self.camera_tilt_angle -= self.camera_step
        self._update_camera_servos()

    def camera_down(self):
        self.camera_tilt_angle += self.camera_step
        self._update_camera_servos()
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Controller for IoT car modes.")
    parser.add_argument("--config", type=str, default="config.json",
                        help="Path to config.json")
    args = parser.parse_args()

    app = CarMonitorApp(args.config)

    # Thread for logging/sending environmental data
    data_thread = threading.Thread(target=app.data_collection_loop, daemon=True)
    data_thread.start()

    sync_thread = threading.Thread(target=app.neon_sync_loop, daemon=True)
    sync_thread.start()
    
    # Main thread runs the drive loop, mode comes from MQTT commands
    app.drive_loop()
