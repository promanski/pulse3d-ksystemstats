# PULSE 3D KSystemStats

A read-only [KSystemStats](https://invent.kde.org/plasma/libksysguard) sensor
script for the Sony PULSE 3D wireless headset and its USB receiver.

The script discovers the device by its USB vendor and product IDs
(`054c:0d5e`) and reads the headset status through HIDAPI. It does not depend
on a fixed `/dev/hidrawN` path, so reconnecting the receiver does not require
reconfiguration.

## Sensors

| Sensor | Value | Range |
| --- | --- | --- |
| `pulse3d_battery` | Headset battery level | `0-100%` |
| `pulse3d_volume` | Hardware master volume | `0-100%` |
| `pulse3d_chat_game` | Chat/game mix | `0-100%` |
| `pulse3d_mute` | Microphone mute state (`1` = muted) | `0-1` |

## Requirements

- KDE Plasma with KSystemStats support
- Python 3
- Linux with HIDAPI's hidraw backend
- A connected Sony PULSE 3D USB receiver

On Debian or Ubuntu, install the runtime dependencies with:

```sh
sudo apt install python3 libhidapi-hidraw0
```

On Arch Linux, install the equivalent packages with:

```sh
sudo pacman -S --needed python hidapi
```

## Installation

Install the script in the per-user KSystemStats scripts directory:

```sh
install -Dm755 pulse3d.py ~/.local/share/ksystemstats/scripts/pulse3d.py
```

Restart Plasma, or log out and in again, so KSystemStats can discover the
script and its sensors.

## Testing

The script speaks the KSystemStats line protocol over standard input/output.
To request one sensor value directly, run:

```sh
printf 'pulse3d_volume\tvalue\n' \
	| ~/.local/share/ksystemstats/scripts/pulse3d.py
```

To list the sensors exposed by the script:

```sh
printf '?\n' | ~/.local/share/ksystemstats/scripts/pulse3d.py
```

If the receiver is unavailable or a reading is temporarily invalid, the
script keeps the last valid value. Before the first valid reading it reports
`0`.

## How It Works

The script reads the `0xB0` HID feature report and converts its status fields
into KSystemStats values. Communication is read-only: no commands are sent to
the headset or receiver.

## Troubleshooting

If all values remain `0`, check that:

1. The PULSE 3D receiver is connected.
2. HIDAPI's hidraw runtime library is installed (`libhidapi-hidraw0` on
   Debian/Ubuntu, or `hidapi` on Arch Linux).
3. The user running KSystemStats can access the matching `/dev/hidraw*`
	 device.

The receiver may expose more than one HID interface. The script selects the
matching existing `hidraw` device automatically.