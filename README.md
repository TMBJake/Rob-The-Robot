# IoT Line Tracking Robot

## Team Members
- **Étienne Khalil** (2230936)  
- **Jake Tremblay** (2330184)

---

## Project Overview
This project consists of building a robot using a Raspberry Pi and having it automated via APIs to steer and take photos of its environment while following a direct path dictated by a black line of tape.  
The robot is designed as a small car that can be steered using our API or automatically through sensors that recognize the path. It also takes photos and uses sensors to analyze its environment, sending the data to a cloud platform so it can be viewed in real time.

The purpose of this project is to show how IoT technology can be combined with robotics to make a system that can autonomously navigate and communicate via cloud-based connections.  
Such a robot can have real-world benefits, such as:
- Detecting unexpected objects or guests in a home.  
- Serving as an automated inspection system in warehouse environments.  
- Performing remote monitoring or data collection as a ground-based drone.

---

## Block Diagram
```plantuml
@startuml
skinparam dpi 150
skinparam componentStyle rectangle
skinparam shadowing false
title IoT Smart Mobile Robot System – Simplified Block Diagram

rectangle "Raspberry Pi 4B" as Pi {
  component "MainCode.py\n(MQTT + Logging)" as main
  component "car.py\n(Control Logic)" as car
}

rectangle "Sensors" as sensors {
  component "IR Line Sensor Array"
  component "Ultrasonic Sensor (HC-SR04)"
  component "ADC Voltage Monitor"
}

rectangle "Actuators" as actuators {
  component "Motor Driver (L298N/TB6612)"
  component "DC Motors (Left/Right)"
  component "Buzzer"
}

cloud "Adafruit IO Cloud\n(MQTT Feeds & Dashboard)" as cloud

sensors --> car : distance / line / voltage data
car --> actuators : PWM motor control
main --> cloud : publish {distance, line_side, voltage}
cloud --> main : remote commands (start/stop/mode)
@enduml
```

# Wiring Diagram and Photos

<img width="875" height="692" alt="Chart" src="https://github.com/user-attachments/assets/3c6dbbdc-ac99-492f-9177-aaf2948468a2" />

<img width="571" height="380" alt="Numbers" src="https://github.com/user-attachments/assets/75be1544-7baf-4bea-bdc6-1b7a0b44b415" />

<img width="868" height="638" alt="Stop" src="https://github.com/user-attachments/assets/bda47ba9-ab95-4bf7-9f08-2292513af1f3" />

![Robo1](https://github.com/user-attachments/assets/5bcc6f13-fcfb-4ecc-9d92-817d53dd1677)

![Robo2](https://github.com/user-attachments/assets/26531e5f-a669-4ab1-bc84-2e947579e54c)

<img width="1338" height="654" alt="Screenshot 2025-11-04 162112" src="https://github.com/user-attachments/assets/623f1758-2ff7-48f4-a7c6-0704edcf36b1" />

<img width="443" height="286" alt="image" src="https://github.com/user-attachments/assets/41da4bb1-eaeb-4e4d-aa1f-2d5e15f4268d" />

https://youtu.be/6_7chIJ2dfs?si=FsjMMmt1L664-Rru

# Setup Instructions

Flash and set up Raspberry Pi OS.

Enable I2C, SPI, and camera using sudo raspi-config.

Connect the sensors, motors, and driver modules according to the wiring diagram.

Install dependencies:
```bash
sudo apt update
sudo apt install python3-pip python3-opencv
pip install adafruit-io gpiozero adafruit-blinka paho-mqtt
```
Edit config.json with your Adafruit IO username and key.

# How to Run

After installing all required files on your Raspberry Pi, enter your Adafruit IO credentials in the JSON configuration file.

In a terminal, navigate to the project directory:
```bash
cd ~/location/of/the/file/ProjectMs2
```
Choose a mode:

infrared – follows a black tape line using IR sensors.

ultrasonic – moves forward and avoids obstacles with ultrasonic sensing.

Run the command:
```bash
python MainCode.py infrared
```
or
```bash
python MainCode.py ultrasonic
```
Press CTRL + C to stop execution.

# What Could Have Gone Better

One of the main difficulties we faced was managing our collaboration since our schedules often conflicted.
This made it challenging to find time to work together consistently, especially during testing and integration.
We also realized that we did not always conduct enough research before beginning each step, which led to avoidable mistakes early on.
Some components took longer to configure than expected because of this lack of preparation.
Despite these issues, we learned to communicate more effectively and plan ahead, which helped us complete the project successfully.
