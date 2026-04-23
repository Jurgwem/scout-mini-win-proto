# Scout Mini CAN App - Install Guide

This guide outlines the steps required to set up and run the AgileX Scout Mini CAN control application on a new Windows machine.

## 1. Hardware Prerequisites
- **AgileX Scout Mini**: Ensure the robot is powered on and the aviation CAN cable is accessible.
- **USB-to-CAN Adapter**: This application uses the `gs_usb` protocol and is optimized for adapters running **candlelight** firmware (e.g., CANable or its clones). Connect it to the Scout Mini's CAN port and plug the USB into your PC.
- **Safety First**: Before running teleoperation testing, ensure the Scout Mini is slightly suspended so the wheels are not touching the ground!

## 2. Windows USB Driver Setup (Zadig)
By default, Windows will assign a generic composite driver to the CANable adapter, which prevents Python from communicating with it directly. You must assign the `WinUSB` driver.

1. Download [Zadig](https://zadig.akeo.ie/).
2. Open Zadig and go to **Options -> List All Devices**.
3. In the dropdown, select your CAN adapter. It may be named **CANable**, **gs_usb**, or **USB-Verbundgerät** (Look for the USB ID `1D50:606F`).
4. If your device shows multiple interfaces (e.g., Interface 0 and Interface 1), select **Interface 0**.
5. Set the Target Driver (on the right) to **WinUSB (v6...)**.
6. Click **Replace Driver** (or Install Driver) and wait for success.

## 3. Python Environment Setup
You must have Python 3 installed. This application uses standard `tkinter` for the GUI and relies on `python-can` with a `libusb` backend for hardware communication.

1. Open a terminal (PowerShell or Command Prompt) in the project folder.
2. Install the required dependencies using pip:
   ```powershell
   pip install -r requirements.txt
   ```
   *(Note: This automatically handles installing `python-can`, `gs_usb`, and crucially the `libusb` bundled backend needed for modern Windows security bypasses).*

## 4. Running the Application
1. In the terminal, execute the script:
   ```powershell
   python main.py
   ```
2. The GUI will appear. The default interface is already set to `gs_usb` at `500000` bps (500 kbps), which is the factory standard for the Scout Mini.
3. Click **Connect**.
4. You can use the **Dashboard** to view live RPM data, the **Telemetry Toggle** to declutter the feed, and the **WASD Controller** to physically drive the robot.
