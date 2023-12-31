import smbus
import time
from ctypes import c_short
import paho.mqtt.client as mqtt

DEVICE = 0x77  # Default device I2C address
bus = smbus.SMBus(1)  # Rev 2 Pi uses 1

# MQTT Configuration
mqtt_broker_address = "raspberrypi"  # Change this to your MQTT broker address
mqtt_topic = "topic1"

def convertToString(data):
    return str((data[1] + (256 * data[0])) / 1.2)

def getShort(data, index):
    return c_short((data[index] << 8) + data[index + 1]).value

def getUshort(data, index):
    return (data[index] << 8) + data[index + 1]

def readBmp180Id(addr=DEVICE):
    REG_ID = 0xD0
    (chip_id, chip_version) = bus.read_i2c_block_data(addr, REG_ID, 2)
    return (chip_id, chip_version)

def readBmp180(addr=0x77):
    REG_CALIB = 0xAA
    REG_MEAS = 0xF4
    REG_MSB = 0xF6
    REG_LSB = 0xF7
    CRV_TEMP = 0x2E
    CRV_PRES = 0x34
    OVERSAMPLE = 3  # 0 - 3

    cal = bus.read_i2c_block_data(addr, REG_CALIB, 22)
    AC1 = getShort(cal, 0)
    AC2 = getShort(cal, 2)
    AC3 = getShort(cal, 4)
    AC4 = getUshort(cal, 6)
    AC5 = getUshort(cal, 8)
    AC6 = getUshort(cal, 10)
    B1 = getShort(cal, 12)
    B2 = getShort(cal, 14)
    MB = getShort(cal, 16)
    MC = getShort(cal, 18)
    MD = getShort(cal, 20)

    bus.write_byte_data(addr, REG_MEAS, CRV_TEMP)
    time.sleep(0.005)
    (msb, lsb) = bus.read_i2c_block_data(addr, REG_MSB, 2)
    UT = (msb << 8) + lsb

    bus.write_byte_data(addr, REG_MEAS, CRV_PRES + (OVERSAMPLE << 6))
    time.sleep(0.04)
    (msb, lsb, xsb) = bus.read_i2c_block_data(addr, REG_MSB, 3)
    UP = ((msb << 16) + (lsb << 8) + xsb) >> (8 - OVERSAMPLE)

    X1 = ((UT - AC6) * AC5) >> 15
    X2 = (MC << 11) / (X1 + MD)
    B5 = X1 + X2
    temperature = int(B5 + 8) >> 4
    temperature = temperature / 10.0

    B6 = B5 - 4000
    B62 = int(B6 * B6) >> 12
    X1 = (B2 * B62) >> 11
    X2 = int(AC2 * B6) >> 11
    X3 = X1 + X2
    B3 = (((AC1 * 4 + X3) << OVERSAMPLE) + 2) >> 2

    X1 = int(AC3 * B6) >> 13
    X2 = (B1 * B62) >> 16
    X3 = ((X1 + X2) + 2) >> 2
    B4 = (AC4 * (X3 + 32768)) >> 15
    B7 = (UP - B3) * (50000 >> OVERSAMPLE)

    P = (B7 * 2) / B4

    X1 = (int(P) >> 8) * (int(P) >> 8)
    X1 = (X1 * 3038) >> 16
    X2 = int(-7357 * P) >> 16
    pressure = int(P + ((X1 + X2 + 3791) >> 4))

    altitude = 44330.0 * (1.0 - pow(pressure / 101325.0, (1.0/5.255)))
    altitude = round(altitude, 2)

    # Publish data to MQTT topic
    mqtt_client = mqtt.Client()
    mqtt_client.connect(mqtt_broker_address, 1883, 10)
    mqtt_client.publish(mqtt_topic, f"Temperature: {temperature} C, Pressure: {pressure} Pa, Altitude: {altitude} m")
    mqtt_client.disconnect()

    return (temperature, pressure, altitude)

if __name__ == "__main__":
    while True:
        data = readBmp180()
        print(f"Temperature: {data[0]} C, Pressure: {data[1]} Pa, Altitude: {data[2]} m")
        time.sleep(5)  # Adjust this value to your desired update interval
