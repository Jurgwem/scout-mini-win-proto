# proto  
> [!NOTE]  
> Vibe-Coded prototype via [Google Antigravity](https://antigravity.google/)  
<br>  
Prototype zur simplen interaktion zwischen Windows und Scout Mini via Python über CAN-Bus  
## Installation / driver  
1. **Download Zadig:** Go to https://zadig.akeo.ie/ and download the Zadig .exe file.  
2. **Open Zadig** (it doesn't need to be installed, it just runs).  
3. **List Devices:** In Zadig's top menu, click Options -> List All Devices.  
4. **Select your Adapter:** In the main dropdown menu, look for your CAN adapter. It will likely be named something like **CANable** or **gs_usb**  
5. **Change the Driver:** Select the **WinUSB**-driver from the dropdown. If there are multiple, select **interface0**  
6. **Apply:** Click the big Replace Driver (or Install Driver) button.  
## Credits  
[LibUSB](https://github.com/libusb/libusb)  
