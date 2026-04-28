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
You must have **Python 3.8+** installed. This application uses standard `tkinter` for the GUI and relies on `python-can` with a `libusb` backend for hardware communication.

> **Important:** On Windows, `python` and `python3` may point to different installations.
> Always use the **same command** for both installing packages and running the app.

1. Open a terminal (PowerShell or Command Prompt) in the project folder.
2. First, check which Python you are using:
   ```powershell
   python --version
   ```
   If this doesn't work, try `python3 --version` instead. Use whichever works for **all** commands below.

3. Install the required dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```
   *(Using `python -m pip` guarantees the packages install into the correct Python. Do **not** use bare `pip` as it may point to a different installation.)*

4. Verify the install succeeded:
   ```powershell
   python -c "import can; import libusb_package; print('All dependencies OK')"
   ```
   You should see `All dependencies OK`. If any `ModuleNotFoundError` appears, re-run step 3.

## 4. Running the Application
1. In the terminal, execute the script:
   ```powershell
   python main.py
   ```
2. The GUI will appear. The default interface is already set to `gs_usb` at `500000` bps (500 kbps), which is the factory standard for the Scout Mini.
3. Click **Connect**.
4. You can use the **Dashboard** to view live RPM data, the **Telemetry Toggle** to declutter the feed, and the **WASD Controller** to physically drive the robot.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No module named 'can'` or `'libusb_package'` | Packages installed under a different Python. Re-run `python -m pip install -r requirements.txt` using the **same** `python` command you use to launch the app. |
| `No backend available` | Zadig driver not installed, or wrong interface selected. Redo Step 2. |
| App connects but no CAN data appears | Scout Mini is off, or CAN H/L wires are swapped. Check wiring. |
| `GsUsbBus was not properly shut down` | Cosmetic warning on exit, safe to ignore. |
