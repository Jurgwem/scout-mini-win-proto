import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import time
import os
import sys

# ---------------------------------------------------------------------------
# Robust libusb backend setup for Windows
# Must run BEFORE importing anything that touches pyusb (including python-can)
# ---------------------------------------------------------------------------
_backend_ok = False
try:
    import libusb_package

    # Strategy 1: Tell pyusb which backend library to load via env var
    _dll_path = str(libusb_package.get_library_path())
    if _dll_path and os.path.isfile(_dll_path):
        os.environ["PYUSB_BACKEND"] = _dll_path
        _dll_dir = os.path.dirname(_dll_path)

        # Strategy 2: Register DLL directory so Windows DLL loader can find it
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(_dll_dir)

        # Strategy 3: Preload the DLL into the process via ctypes
        import ctypes
        try:
            ctypes.cdll.LoadLibrary(_dll_path)
        except OSError:
            ctypes.WinDLL(_dll_path)

    # Strategy 4: Obtain a working backend object and monkey-patch usb.core.find
    import usb.core
    import usb.backend.libusb1
    _be = usb.backend.libusb1.get_backend(find_library=libusb_package.find_library)

    if _be is not None:
        _orig_find = usb.core.find

        def _patched_find(*args, **kwargs):
            if "backend" not in kwargs:
                kwargs["backend"] = _be
            return _orig_find(*args, **kwargs)

        usb.core.find = _patched_find

        # Strategy 5: Patch the gs_usb module's own cached reference (if loaded)
        try:
            import gs_usb.gs_usb as _gs_mod
            if hasattr(_gs_mod, "usb"):
                _gs_mod.usb.core.find = _patched_find
        except Exception:
            pass

        _backend_ok = True

except Exception as e:
    print(f"Warning: libusb backend setup failed: {e}")

if not _backend_ok:
    print("WARNING: No libusb backend was loaded. CAN connection will likely fail.")
    print("         Make sure 'pip install libusb-package' succeeded.")

# Now safe to import python-can (which internally imports gs_usb / pyusb)
import can


class ScoutCANTestApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AgileX Scout Mini CAN Test App")
        self.root.geometry("700x500")

        self.bus = None
        self.running = False
        self.test_mode = False
        self.msg_count = 0
        self.msg_queue = queue.Queue()

        self.setup_ui()
        self.root.after(100, self.process_queue)

    def setup_ui(self):
        # Connection Frame
        conn_frame = ttk.LabelFrame(self.root, text="CAN Connection")
        conn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(conn_frame, text="Interface:").grid(row=0, column=0, padx=5, pady=5)
        self.interface_var = tk.StringVar(value="gs_usb")
        ttk.Entry(conn_frame, textvariable=self.interface_var, width=15).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(conn_frame, text="Channel/Port:").grid(row=0, column=2, padx=5, pady=5)
        self.channel_var = tk.StringVar(value="0") # Typical for gs_usb or slcan
        ttk.Entry(conn_frame, textvariable=self.channel_var, width=15).grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(conn_frame, text="Bitrate:").grid(row=0, column=4, padx=5, pady=5)
        self.bitrate_var = tk.StringVar(value="500000")
        ttk.Entry(conn_frame, textvariable=self.bitrate_var, width=10).grid(row=0, column=5, padx=5, pady=5)

        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self.toggle_connect)
        self.connect_btn.grid(row=0, column=6, padx=10, pady=5)

        # Status and Test Frame
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        self.status_lbl = ttk.Label(control_frame, text="Status: Disconnected", foreground="red")
        self.status_lbl.pack(side=tk.LEFT, padx=5)

        self.test_btn = ttk.Button(control_frame, text="Run Test Sequence", command=self.run_test, state=tk.DISABLED)
        self.test_btn.pack(side=tk.RIGHT, padx=5)

        self.filter_var = tk.BooleanVar(value=False)
        self.filter_chk = ttk.Checkbutton(control_frame, text="Hide System Telemetry", variable=self.filter_var)
        self.filter_chk.pack(side=tk.RIGHT, padx=15)

        self.dashboard_btn = ttk.Button(control_frame, text="Open Dashboard", command=self.open_dashboard)
        self.dashboard_btn.pack(side=tk.RIGHT, padx=5)

        self.controller_btn = ttk.Button(control_frame, text="Open Controller", command=self.open_controller)
        self.controller_btn.pack(side=tk.RIGHT, padx=5)

        # Data Display Frame
        data_frame = ttk.LabelFrame(self.root, text="CAN Message Feed")
        data_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.text_area = tk.Text(data_frame, state=tk.DISABLED, wrap=tk.WORD, font=("Consolas", 10))
        self.text_area.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scrollbar = ttk.Scrollbar(data_frame, command=self.text_area.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_area.configure(yscrollcommand=scrollbar.set)

    def log(self, msg):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.insert(tk.END, msg + "\n")
        self.text_area.see(tk.END)
        # Keep only the last 1000 lines
        lines = int(self.text_area.index('end-1c').split('.')[0])
        if lines > 1000:
            self.text_area.delete('1.0', f'{lines-1000}.0')
        self.text_area.config(state=tk.DISABLED)

    def toggle_connect(self):
        if self.running:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        interface = self.interface_var.get()
        channel = self.channel_var.get()
        bitrate = int(self.bitrate_var.get())

        if channel.isdigit():
            # For gs_usb it's usually an integer index
            channel = int(channel)

        try:
            self.bus = can.interface.Bus(interface=interface, channel=channel, bitrate=bitrate)
            self.running = True
            
            self.connect_btn.config(text="Disconnect")
            self.status_lbl.config(text=f"Status: Connected to {interface}:{channel}", foreground="green")
            self.test_btn.config(state=tk.NORMAL)
            self.log(f"--- Connected to {interface} on channel {channel} at {bitrate}bps ---")

            self.recv_thread = threading.Thread(target=self.receive_loop, daemon=True)
            self.recv_thread.start()

        except Exception as e:
            if self.bus:
                self.bus.shutdown()
                self.bus = None
            messagebox.showerror("Connection Error", str(e))
            self.log(f"Error connecting: {e}")

    def disconnect(self):
        self.running = False
        if hasattr(self, 'recv_thread') and self.recv_thread.is_alive():
            # Let the thread cleanly break out of its loop
            self.root.update() 
            
        if self.bus:
            try:
                self.bus.shutdown()
            except Exception as e:
                self.log(f"Shutdown warning: {e}")
            finally:
                self.bus = None
            
        self.connect_btn.config(text="Connect")
        self.status_lbl.config(text="Status: Disconnected", foreground="red")
        self.test_btn.config(state=tk.DISABLED)
        self.log("--- Disconnected ---")

    def receive_loop(self):
        while self.running and self.bus:
            try:
                msg = self.bus.recv(0.1) # 100ms timeout
                if msg is not None:
                    self.msg_queue.put(msg)
            except Exception as e:
                pass # Can happen on disconnect cleanly

    def process_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()

                if self.test_mode:
                    self.msg_count += 1

                # Update live dashboard if open
                if msg.arbitration_id in {0x251, 0x252, 0x253, 0x254}:
                    if hasattr(self, 'wheel_vars') and getattr(self, 'dash_window', None) and self.dash_window.winfo_exists():
                        val = (msg.data[0] << 8) | msg.data[1]
                        if val > 32767:
                            val -= 65536
                        self.wheel_vars[msg.arbitration_id].set(f"{val} RPM")

                if self.filter_var.get():
                    # Always hide these repeating background systems
                    if msg.arbitration_id in {0x241, 0x311, 0x261, 0x262, 0x263, 0x264, 0x211, 0x231}:
                        continue
                    # Hide motor/velocity IDs ONLY when they are completely stopped (all zeros)
                    if msg.arbitration_id in {0x251, 0x252, 0x253, 0x254, 0x221}:
                        if all(b == 0 for b in msg.data):
                            continue

                data_hex = " ".join([f"{b:02X}" for b in msg.data])
                msg_str = f"Time: {msg.timestamp:.3f} | ID: 0x{msg.arbitration_id:03X} | DLC: {msg.dlc} | Data: {data_hex}"
                self.log(msg_str)

        except queue.Empty:
            pass

        self.root.after(50, self.process_queue)

    def run_test(self):
        if not self.running:
            return
            
        self.test_mode = True
        self.msg_count = 0
        self.test_btn.config(state=tk.DISABLED, text="Testing...")
        self.log("\n>>> STARTING CONNECTION TEST <<<")
        self.log("Listening for continuous messages from Scout Mini... (Waiting 3 seconds)\n")

        # Give it 3 seconds to collect frames
        self.root.after(3000, self.evaluate_test)

    def evaluate_test(self):
        self.test_mode = False
        self.test_btn.config(state=tk.NORMAL, text="Run Test Sequence")
        
        self.log(f"\n>>> TEST COMPLETE. Received {self.msg_count} CAN frames in 3 seconds. <<<")
        if self.msg_count > 5:
            self.log("RESULT: PASS - Communication with Scout Mini is active.")
            messagebox.showinfo("Test Result", "PASS - Connection is solid and data is streaming.")
        else:
            self.log("RESULT: FAIL - No or very few messages received.")
            self.log("Troubleshooting:")
            self.log("1. Is the Scout Mini turned on?")
            self.log("2. Are the CAN High/Low pins correctly connected?")
            self.log("3. Is the bitrate exactly 500000?")
            messagebox.showwarning("Test Result", "FAIL - Could not detect data from Scout Mini. Check your wiring and power.")

    def open_dashboard(self):
        if hasattr(self, 'dash_window') and getattr(self, 'dash_window', None) and self.dash_window.winfo_exists():
            self.dash_window.lift()
            return

        self.dash_window = tk.Toplevel(self.root)
        self.dash_window.title("Wheel RPM Dashboard")
        self.dash_window.geometry("340x200")
        
        self.wheel_vars = {
            0x251: tk.StringVar(value="0 RPM"),
            0x252: tk.StringVar(value="0 RPM"),
            0x253: tk.StringVar(value="0 RPM"),
            0x254: tk.StringVar(value="0 RPM"),
        }
        
        ttk.Label(self.dash_window, text="Motor 1 (FR)", font=("Helvetica", 10, "bold")).grid(row=0, column=0, padx=25, pady=(20,5))
        ttk.Label(self.dash_window, textvariable=self.wheel_vars[0x251], font=("Helvetica", 16)).grid(row=1, column=0, padx=25)

        ttk.Label(self.dash_window, text="Motor 2 (FL)", font=("Helvetica", 10, "bold")).grid(row=0, column=1, padx=25, pady=(20,5))
        ttk.Label(self.dash_window, textvariable=self.wheel_vars[0x252], font=("Helvetica", 16)).grid(row=1, column=1, padx=25)

        ttk.Label(self.dash_window, text="Motor 3 (RR)", font=("Helvetica", 10, "bold")).grid(row=2, column=0, padx=25, pady=(20,5))
        ttk.Label(self.dash_window, textvariable=self.wheel_vars[0x253], font=("Helvetica", 16)).grid(row=3, column=0, padx=25)

        ttk.Label(self.dash_window, text="Motor 4 (RL)", font=("Helvetica", 10, "bold")).grid(row=2, column=1, padx=25, pady=(20,5))
        ttk.Label(self.dash_window, textvariable=self.wheel_vars[0x254], font=("Helvetica", 16)).grid(row=3, column=1, padx=25)

    def open_controller(self):
        if hasattr(self, 'ctrl_window') and getattr(self, 'ctrl_window', None) and self.ctrl_window.winfo_exists():
            self.ctrl_window.lift()
            return

        if not self.running or not self.bus:
            messagebox.showwarning("Not Connected", "Please connect to the CAN bus first!")
            return

        self.ctrl_window = tk.Toplevel(self.root)
        self.ctrl_window.title("WASD Controller")
        self.ctrl_window.geometry("350x250")
        
        ttk.Label(self.ctrl_window, text="WASD Controller", font=("Helvetica", 14, "bold")).pack(pady=10)
        ttk.Label(self.ctrl_window, text="Press and hold W/A/S/D to drive.", font=("Helvetica", 10)).pack()
        
        # Dynamic RPM Slider
        slider_frame = ttk.Frame(self.ctrl_window)
        slider_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Label(slider_frame, text="Target RPM:").pack(side=tk.LEFT)
        self.rpm_var = tk.IntVar(value=100)
        
        rpm_slider = ttk.Scale(slider_frame, from_=0, to=400, variable=self.rpm_var, orient='horizontal', 
                               command=lambda s: self.rpm_var.set(int(float(s))))
        rpm_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        ttk.Label(slider_frame, textvariable=self.rpm_var, font=("Helvetica", 10, "bold"), width=3).pack(side=tk.RIGHT)

        ttk.Label(self.ctrl_window, text="Ensure wheels are suspended!", font=("Helvetica", 10, "bold"), foreground="red").pack(pady=5)
        
        self.keys = {'w': False, 'a': False, 's': False, 'd': False}
        
        def key_press(event):
            k = event.keysym.lower()
            if k in self.keys:
                self.keys[k] = True

        def key_release(event):
            k = event.keysym.lower()
            if k in self.keys:
                self.keys[k] = False

        self.ctrl_window.bind("<KeyPress>", key_press)
        self.ctrl_window.bind("<KeyRelease>", key_release)
        self.ctrl_window.focus_set()

        # Send enable CAN control command initially 
        try:
            enable_msg = can.Message(arbitration_id=0x421, data=[0x01, 0, 0, 0, 0, 0, 0, 0], is_extended_id=False)
            self.bus.send(enable_msg)
        except:
            pass

        self.ctrl_running = True
        
        def ctrl_loop():
            if not getattr(self, 'ctrl_running', False) or not self.ctrl_window.winfo_exists():
                return

            if self.bus:
                current_rpm = self.rpm_var.get()
                linear_val = int(current_rpm * 8.3)
                angular_val = int(current_rpm * 10)

                linear = linear_val * (self.keys['w'] - self.keys['s'])    # forward/back mm/s
                angular = angular_val * (self.keys['a'] - self.keys['d'])  # turn rad/s
                
                # Convert to big-endian 16-bit
                data = bytearray(8)
                data[0] = (linear >> 8) & 0xFF
                data[1] = linear & 0xFF
                data[2] = (angular >> 8) & 0xFF
                data[3] = angular & 0xFF
                
                try:
                    motion_msg = can.Message(arbitration_id=0x111, data=data, is_extended_id=False)
                    self.bus.send(motion_msg)
                except Exception:
                    pass
            
            # Keep sending frame at ~50Hz (20ms interval) for safety timeout heartbeat constraints
            self.root.after(20, ctrl_loop)

        # Start control loop
        ctrl_loop()
        
        def ctrl_close():
            self.ctrl_running = False
            self.ctrl_window.destroy()
            
        self.ctrl_window.protocol("WM_DELETE_WINDOW", ctrl_close)

    def on_closing(self):
        self.disconnect()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ScoutCANTestApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
