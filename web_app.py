import asyncio
import json
import os
import sys
import threading
import time
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# ---------------------------------------------------------------------------
# Robust libusb backend setup for Windows
# Must run BEFORE importing anything that touches pyusb (including python-can)
# ---------------------------------------------------------------------------
_backend_ok = False
_dll_path = None
_script_dir = os.path.dirname(os.path.abspath(__file__))

_local_dll = os.path.join(_script_dir, "libusb-1.0.dll")
if os.path.isfile(_local_dll):
    _dll_path = _local_dll
    print(f"[DEBUG] Found local DLL: {_dll_path}")

if not _dll_path:
    try:
        import libusb_package
        _raw = libusb_package.get_library_path()
        if _raw and os.path.isfile(str(_raw)):
            _dll_path = str(_raw)
            print(f"[DEBUG] Found DLL via libusb_package: {_dll_path}")
    except ImportError:
        pass

if _dll_path:
    import ctypes
    _dll_dir = os.path.dirname(_dll_path)
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(_dll_dir)
    try:
        ctypes.cdll.LoadLibrary(_dll_path)
    except OSError:
        try:
            ctypes.WinDLL(_dll_path)
        except OSError:
            pass
    os.environ["PYUSB_BACKEND"] = _dll_path

try:
    import usb.core
    import usb.backend.libusb1

    def _custom_find_library(candidate):
        return _dll_path

    _be = usb.backend.libusb1.get_backend(find_library=_custom_find_library if _dll_path else None)
    if _be is not None:
        _orig_find = usb.core.find
        def _patched_find(*args, **kwargs):
            if "backend" not in kwargs:
                kwargs["backend"] = _be
            return _orig_find(*args, **kwargs)
        usb.core.find = _patched_find

        try:
            import gs_usb.gs_usb as _gs_mod
            if hasattr(_gs_mod, "usb"):
                _gs_mod.usb.core.find = _patched_find
        except Exception:
            pass
        _backend_ok = True
except Exception as e:
    pass

import can

# ---------------------------------------------------------------------------
# App Logic
# ---------------------------------------------------------------------------

app = FastAPI()

# Mount static files
static_dir = os.path.join(_script_dir, "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

class ScoutCANManager:
    def __init__(self):
        self.bus = None
        self.running = False
        self.filter_telemetry = False
        self.active_connections: Set[WebSocket] = set()
        self.loop = None
        
        # WASD state
        self.keys = {'w': False, 'a': False, 's': False, 'd': False}
        self.target_rpm = 100
        
    def set_loop(self, loop):
        self.loop = loop

    async def connect_client(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        # Send current status
        status_msg = "Connected" if self.running else "Disconnected"
        await websocket.send_text(json.dumps({"type": "status", "status": status_msg}))
        await websocket.send_text(json.dumps({"type": "rpm_target", "value": self.target_rpm}))
        await websocket.send_text(json.dumps({"type": "filter_state", "value": self.filter_telemetry}))

    def disconnect_client(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        msg_str = json.dumps(message)
        dead_connections = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(msg_str)
            except Exception:
                dead_connections.add(connection)
        
        for dead in dead_connections:
            self.disconnect_client(dead)

    def thread_safe_broadcast(self, message: dict):
        if self.loop and self.active_connections:
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)

    def connect(self, interface="gs_usb", channel=0, bitrate=500000):
        if self.running:
            return True, "Already connected"
            
        try:
            if isinstance(channel, str) and channel.isdigit():
                channel = int(channel)
                
            self.bus = can.interface.Bus(interface=interface, channel=channel, bitrate=bitrate)
            self.running = True
            
            # Enable control
            try:
                enable_msg = can.Message(arbitration_id=0x421, data=[0x01, 0, 0, 0, 0, 0, 0, 0], is_extended_id=False)
                self.bus.send(enable_msg)
            except Exception:
                pass

            self.recv_thread = threading.Thread(target=self.receive_loop, daemon=True)
            self.recv_thread.start()
            
            self.ctrl_thread = threading.Thread(target=self.control_loop, daemon=True)
            self.ctrl_thread.start()

            self.thread_safe_broadcast({"type": "status", "status": "Connected"})
            self.thread_safe_broadcast({"type": "log", "message": f"--- Connected to {interface}:{channel} @ {bitrate}bps ---"})
            return True, "Connected successfully"
        except Exception as e:
            return False, str(e)

    def disconnect(self):
        self.running = False
        time.sleep(0.1) # Let threads exit cleanly
        if self.bus:
            try:
                self.bus.shutdown()
            except Exception:
                pass
            self.bus = None
        self.thread_safe_broadcast({"type": "status", "status": "Disconnected"})
        self.thread_safe_broadcast({"type": "log", "message": "--- Disconnected ---"})

    def receive_loop(self):
        while self.running and self.bus:
            try:
                msg = self.bus.recv(0.1)
                if msg is not None:
                    # RPM parsing
                    if msg.arbitration_id in {0x251, 0x252, 0x253, 0x254}:
                        val = (msg.data[0] << 8) | msg.data[1]
                        if val > 32767:
                            val -= 65536
                        self.thread_safe_broadcast({"type": "rpm", "id": msg.arbitration_id, "value": val})
                    
                    # Filtering
                    if self.filter_telemetry:
                        if msg.arbitration_id in {0x241, 0x311, 0x261, 0x262, 0x263, 0x264, 0x211, 0x231}:
                            continue
                        if msg.arbitration_id in {0x251, 0x252, 0x253, 0x254, 0x221}:
                            if all(b == 0 for b in msg.data):
                                continue

                    data_hex = " ".join([f"{b:02X}" for b in msg.data])
                    msg_str = f"Time: {msg.timestamp:.3f} | ID: 0x{msg.arbitration_id:03X} | DLC: {msg.dlc} | Data: {data_hex}"
                    self.thread_safe_broadcast({"type": "log", "message": msg_str})
            except Exception:
                pass

    def control_loop(self):
        while self.running and self.bus:
            linear_val = int(self.target_rpm * 8.3)
            angular_val = int(self.target_rpm * 10)

            linear = linear_val * (self.keys['w'] - self.keys['s'])
            angular = angular_val * (self.keys['a'] - self.keys['d'])
            
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
            
            time.sleep(0.02) # ~50Hz

can_manager = ScoutCANManager()

@app.on_event("startup")
async def startup_event():
    can_manager.set_loop(asyncio.get_running_loop())

@app.on_event("shutdown")
def shutdown_event():
    can_manager.disconnect()

@app.get("/")
async def get_index():
    return FileResponse(os.path.join(_script_dir, "static", "index.html"))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await can_manager.connect_client(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            if msg["type"] == "connect":
                success, error_msg = can_manager.connect(msg.get("interface", "gs_usb"), msg.get("channel", "0"), msg.get("bitrate", 500000))
                if not success:
                    await websocket.send_text(json.dumps({"type": "error", "message": error_msg}))
            
            elif msg["type"] == "disconnect":
                can_manager.disconnect()
                
            elif msg["type"] == "key":
                k = msg["key"]
                state = msg["state"] # true for down, false for up
                if k in can_manager.keys:
                    can_manager.keys[k] = state
                    
            elif msg["type"] == "rpm":
                can_manager.target_rpm = int(msg["value"])
                
            elif msg["type"] == "filter":
                can_manager.filter_telemetry = bool(msg["value"])
                
    except WebSocketDisconnect:
        can_manager.disconnect_client(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
