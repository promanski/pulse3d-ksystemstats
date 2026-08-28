#!/usr/bin/env python3

import ctypes
import ctypes.util
import os
import sys


VID = 0x054C
PID = 0x0D5E
REPORT_ID = 0xB0
REPORT_SIZE = 65


SENSORS = (
    "pulse3d_battery",
    "pulse3d_volume",
    "pulse3d_chat_game",
    "pulse3d_mute",
)


class HidDeviceInfo(ctypes.Structure):
    pass


HidDeviceInfo._fields_ = [
    ("path", ctypes.c_char_p),
    ("vendor_id", ctypes.c_ushort),
    ("product_id", ctypes.c_ushort),
    ("serial_number", ctypes.c_wchar_p),
    ("release_number", ctypes.c_ushort),
    ("manufacturer_string", ctypes.c_wchar_p),
    ("product_string", ctypes.c_wchar_p),
    ("usage_page", ctypes.c_ushort),
    ("usage", ctypes.c_ushort),
    ("interface_number", ctypes.c_int),
    ("next", ctypes.POINTER(HidDeviceInfo)),
]


# ----------------------------------------------------------------------
# HIDAPI
# ----------------------------------------------------------------------

def load_hidapi():
    name = (
        ctypes.util.find_library("hidapi-hidraw")
        or "libhidapi-hidraw.so"
    )

    try:
        return ctypes.CDLL(name)
    except OSError as error:
        print(
            f"ERROR: cannot load hidapi: {error}",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)


hid = load_hidapi()

hid.hid_init.restype = ctypes.c_int
hid.hid_exit.restype = ctypes.c_int

hid.hid_enumerate.argtypes = [
    ctypes.c_ushort,
    ctypes.c_ushort,
]
hid.hid_enumerate.restype = ctypes.POINTER(HidDeviceInfo)

hid.hid_free_enumeration.argtypes = [
    ctypes.POINTER(HidDeviceInfo)
]
hid.hid_free_enumeration.restype = None

hid.hid_open_path.argtypes = [ctypes.c_char_p]
hid.hid_open_path.restype = ctypes.c_void_p

hid.hid_close.argtypes = [ctypes.c_void_p]
hid.hid_close.restype = None

hid.hid_get_feature_report.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_ubyte),
    ctypes.c_size_t,
]
hid.hid_get_feature_report.restype = ctypes.c_int

hid.hid_error.argtypes = [ctypes.c_void_p]
hid.hid_error.restype = ctypes.c_wchar_p


# ----------------------------------------------------------------------
# Device discovery
# ----------------------------------------------------------------------

def find_device():
    """
    Find the current Sony PULSE 3D HID device.

    We search by VID/PID instead of using a fixed hidraw number because
    /dev/hidrawN may change after unplugging and reconnecting the dongle.
    """

    devices = hid.hid_enumerate(VID, PID)

    if not devices:
        return None

    try:
        current = devices

        while current:
            path = current.contents.path

            if path:
                decoded = path.decode(errors="replace")

                if (
                    decoded.startswith("/dev/hidraw")
                    and os.path.exists(decoded)
                ):
                    return decoded

            current = current.contents.next

    finally:
        hid.hid_free_enumeration(devices)

    return None


def open_device():
    """Find and open the current PULSE 3D HID device."""

    path = find_device()

    if not path:
        return None

    device = hid.hid_open_path(path.encode())

    if not device:
        return None

    return device


# ----------------------------------------------------------------------
# PULSE 3D B0 report
# ----------------------------------------------------------------------

def read_b0(device):
    """
    Read the PULSE 3D B0 status report.

    The receiver requires:

        GET_FEATURE
        report ID = 0xB0
        request buffer = 65 bytes

    Known fields:

        B0[2] = chat/game
        B0[3] = battery candidate
        B0[4] = mute
        B0[5] = composite state
        B0[7] = master volume
    """

    buffer = (ctypes.c_ubyte * REPORT_SIZE)()

    buffer[0] = REPORT_ID

    count = hid.hid_get_feature_report(
        device,
        buffer,
        REPORT_SIZE,
    )

    if count < 0:
        return None

    if count < 8:
        return None

    if buffer[0] != REPORT_ID:
        return None

    return bytes(buffer[:8])


# ----------------------------------------------------------------------
# Sensor conversion
# ----------------------------------------------------------------------

def get_value(sensor, data):
    """
    Convert one B0 report into a KSystemStats value.

    Invalid/transitional values are returned as None so that the caller
    can preserve the last known good value.
    """

    if data is None:
        return None

    # --------------------------------------------------------------
    # Battery
    # --------------------------------------------------------------

    if sensor == "pulse3d_battery":

        battery = data[3]

        # 0x80 is a known USB/charging transition state.
        if battery == 0x80:
            return None

        if 0 <= battery <= 100:
            return str(battery)

        return None

    # --------------------------------------------------------------
    # Master volume
    # --------------------------------------------------------------

    if sensor == "pulse3d_volume":

        volume = data[7]

        # Prevent transient values such as 0xFF (255) from appearing
        # in KDE as 255%.
        if 0 <= volume <= 100:
            return str(volume)

        return None

    # --------------------------------------------------------------
    # Chat/Game
    # --------------------------------------------------------------

    if sensor == "pulse3d_chat_game":

        chat_game = data[2]

        if 0 <= chat_game <= 100:
            return str(chat_game)

        return None

    # --------------------------------------------------------------
    # Mute
    # --------------------------------------------------------------

    if sensor == "pulse3d_mute":

        # Confirmed states from physical testing:
        #
        # 0xEF = muted
        # 0xED = unmuted

        if data[4] == 0xEF:
            return "1"

        if data[4] == 0xED:
            return "0"

        return None

    return None


# ----------------------------------------------------------------------
# Sensor metadata
# ----------------------------------------------------------------------

def get_property(sensor, prop):

    properties = {

        "pulse3d_battery": {
            "initial_value": "0",
            "name": "PULSE 3D Battery",
            "short_name": "PULSE 3D",
            "description": "Sony PULSE 3D headset battery level",
            "min": "0",
            "max": "100",
            "unit": "%",
            "variant_type": "double",
        },

        "pulse3d_volume": {
            "initial_value": "0",
            "name": "PULSE 3D Volume",
            "short_name": "PULSE 3D Vol",
            "description": "Sony PULSE 3D master volume",
            "min": "0",
            "max": "100",
            "unit": "%",
            "variant_type": "double",
        },

        "pulse3d_chat_game": {
            "initial_value": "0",
            "name": "PULSE 3D Chat/Game",
            "short_name": "Chat/Game",
            "description": "Sony PULSE 3D chat/game value",
            "min": "0",
            "max": "100",
            "unit": "%",
            "variant_type": "double",
        },

        "pulse3d_mute": {
            "initial_value": "0",
            "name": "PULSE 3D Mute",
            "short_name": "Mute",
            "description": "Sony PULSE 3D microphone mute state",
            "min": "0",
            "max": "1",
            "unit": "-",
            "variant_type": "double",
        },
    }

    return properties.get(sensor, {}).get(prop, "")


# ----------------------------------------------------------------------
# Dynamic value reading + reconnect
# ----------------------------------------------------------------------

def read_current_value(sensor):
    """
    Read a sensor value with automatic HID reconnect.

    If the dongle is unplugged:

        old HID handle -> discarded
        device -> None

    On the next request:

        find_device() -> new /dev/hidrawN
        open_device() -> new HID handle

    The hidraw number therefore does not matter.
    """

    global device
    global last_values

    # --------------------------------------------------------------
    # No active HID connection
    # --------------------------------------------------------------

    if device is None:

        device = open_device()

        if device is None:

            # No dongle currently available.
            # Preserve the last known good value.
            return last_values.get(sensor)

    # --------------------------------------------------------------
    # Read current B0
    # --------------------------------------------------------------

    data = read_b0(device)

    # --------------------------------------------------------------
    # HID handle became invalid
    # --------------------------------------------------------------

    if data is None:

        try:
            hid.hid_close(device)
        except Exception:
            pass

        device = None

        # Do not replace the last good value with 0.
        return last_values.get(sensor)

    # --------------------------------------------------------------
    # Convert and validate
    # --------------------------------------------------------------

    value = get_value(sensor, data)

    # --------------------------------------------------------------
    # Invalid/transitional value
    # --------------------------------------------------------------

    if value is None:

        # Keep previous valid reading.
        return last_values.get(sensor)

    # --------------------------------------------------------------
    # Valid value
    # --------------------------------------------------------------

    last_values[sensor] = value

    return value


# ----------------------------------------------------------------------
# Main KSystemStats protocol
# ----------------------------------------------------------------------

def main():

    global device
    global last_values

    device = None

    # Last known good values.
    #
    # This prevents temporary HID failures or transitional B0 values
    # from turning a perfectly valid sensor into 0.
    last_values = {
        "pulse3d_battery": "0",
        "pulse3d_volume": "0",
        "pulse3d_chat_game": "0",
        "pulse3d_mute": "0",
    }

    if hid.hid_init() != 0:
        sys.exit(1)

    try:

        for line in sys.stdin:

            line = line.rstrip("\r\n")

            if not line:
                continue

            parts = line.split("\t")

            request = parts[0]

            # ------------------------------------------------------
            # Sensor discovery
            # ------------------------------------------------------

            if request == "?":

                print(
                    "\t".join(SENSORS),
                    flush=True,
                )

                continue

            # ------------------------------------------------------
            # Unknown sensor
            # ------------------------------------------------------

            if request not in SENSORS:

                print(
                    "",
                    flush=True,
                )

                continue

            prop = parts[1] if len(parts) > 1 else ""

            # ------------------------------------------------------
            # Static properties
            # ------------------------------------------------------

            if prop != "value":

                print(
                    get_property(request, prop),
                    flush=True,
                )

                continue

            # ------------------------------------------------------
            # Dynamic sensor value
            # ------------------------------------------------------

            value = read_current_value(request)

            # If there has never been a valid reading, return 0.
            if value is None:
                value = "0"

            print(
                value,
                flush=True,
            )

    except BrokenPipeError:
        pass

    finally:

        if device is not None:

            try:
                hid.hid_close(device)
            except Exception:
                pass

            device = None

        hid.hid_exit()


if __name__ == "__main__":
    main()
