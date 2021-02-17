# psp-120-remote-tool
Python tool to talk to PSP-120 remote. 
It inits the remote, maintains communication, and receives any key presses/releases. Also, it sends common multimedia scancodes, to control your playback.

Inspiration: connect it directly to the Raspberry Pi SBC and use some form of user input, or connect it to Raspberry Pi pico and use this script with micropython as USB keyboard.
_TODO: branch for RPi pico._

## hardware
The remote is a serial device, it talks @ baud 4800,8N1. CTS line is avaliable and it is asserted when ⏯️ button is pressed.

### pinout
![PSP 120 internals pinout](https://github.com/amateusz/psp-120-remote-tool/blob/main/psp_120_remote_pinout.png)

where:

`D-`  - digital ground

`A-`  - analog ground

`L/R` - left or right audio channel, idk
___


The remote is 2V5 device, so make sure to level-convert data lines. I guess it should be fine with 3V3. I used cheap MOSFET level-converter and silicon diode to drop 3V3→2V6 which is close enough.
The remote expects an answer within first few seconds after power up, so we need to have control over its power line. I'm using separate P-channel MOSFET, but flow control lines of e.g. FT232 adapter should be enough.

## protocol
I've done initial coding with help of this guide: http://mc.pp.se/psp/phones.xhtml, but it proved to be missing.
Current implementation is based on sniffing the PSP-1000 ↔ PSP-120 traffic. The dump is included in the repo.

Initial communication (first 2 packets)
![psp-remote-initial-comms](https://user-images.githubusercontent.com/9356928/108277141-3b9c1b80-7179-11eb-900e-49e31ea08a73.png)

Every packet needs to be "answered" and "ack"ed.

### The communicatoin goes like this:
- PSP provides power to the remote
- remote sends some 2 commands
  - PSP acks each one
- remote sends initial button state
  - PSP acks
from now on
- the PSP sends a "keepalive" packet every 1 second
  - remote acks
- on keypress/release remote sends key packet
  - PSP acks

Seems like the LSB of the command byte is some kind of checksum, as command bytes `0x02`/`0x03` are used interchangeably, same goes for `0x84`/`0x85`. Current implementation treats them as distinct commands though.

## usage
`sudo python3 psp-120-remote-tool.py`
sudo is required due to module `keyboard` to simulate keypresses

---

There is a Pulseview dump of the communication between the remote and PSP which I based this code on
