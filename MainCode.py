#Add lab 6 parts to this
from car import Car
import argparse
import time
import logging
import os
import paho.mqtt.client as mqtt
import threading
import json
from datetime import datetime

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
            self.setup_mqtt()

    def load_config(self, config_file):
        """Load configuration from JSON file"""
        default_config = {
            "ADAFRUIT_IO_USERNAME": "username",
            "ADAFRUIT_IO_KEY": "userkey",
            "MQTT_BROKER": "io.adafruit.com",
            "MQTT_PORT": 1883,
            "MQTT_KEEPALIVE": 60,
            "devices": ["living_room_light", "bedroom_fan", "front_door", "garage_door"],
            "camera_enabled": True,
            "capturing_interval": 5,
            "flushing_interval": 10,
            "sync_interval": 300
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

    def run_ultrasonic_mode(self, duration=None):
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
            self.car.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Controller for IoT car modes.")
    parser.add_argument("mode", choices=["ultrasonic", "infrared"], help="Which mode to run")
    parser.add_argument("--duration", type=int, default=None,
                        help="How long to run (in seconds). Leave empty for infinite.")
    parser.add_argument("--config", type=str, default="config.json",
                        help="Path to config.json")
    args = parser.parse_args()
    
    app = CarMonitorApp(args.config)
    
    data_thread = threading.Thread(target=app.data_collection_loop)
    data_thread.start()

    if args.mode == "ultrasonic":
        app.run_ultrasonic_mode(args.duration)
    else:
        app.run_infrared_mode(args.duration)
