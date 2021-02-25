from time import sleep

from sys import platform, stderr

if platform == 'linux':
    from datetime import datetime as dt
    
    from serial import Serial
    import keyboard
    
    remote = Serial('/dev/ttyUSB0', baudrate=4800)
    remote.timeout = .30 # 30 ms is plenty to recv the packet
    
    def turn(state: bool):
        if state:
            remote.setRTS(False)
        else:
            remote.setRTS(True)
        print(f'turn {state}')
        
    def seconds_since(since):
        return (dt.now() - since).seconds
    
    
    def timestamp_now():
        return dt.now()
    
    BUTTONS_OUT = {'⏯️'   : 164,
           '⏭️'   : 163,
           '⏮️'   : 165,
           '+'   : 115,
           '-'   : 114,
           'HOLD': 113,
           }
    
    def key_press(key):
        keyboard.press(BUTTONS_OUT[key])
        
    def key_release(key):
        keyboard.release(BUTTONS_OUT[key])        
            
elif platform == 'RP2040':
    import usb_hid
    from adafruit_hid.consumer_control_code import ConsumerControlCode
    from adafruit_hid.consumer_control import ConsumerControl
    keyboard_multimedia = ConsumerControl(usb_hid.devices)
    
    from adafruit_hid.keyboard import Keyboard
    from adafruit_hid.keycode import Keycode

    keyboard = Keyboard(usb_hid.devices)
    
    import rtc 
    r = rtc.RTC()

    import board
    import busio
    
    remote = busio.UART(board.GP16, board.GP17, baudrate=4800)
    remote.timeout = .8
    
    import digitalio 
    
    turnPin = digitalio.DigitalInOut(board.GP2)
    turnPin.direction = digitalio.Direction.OUTPUT
    
    def turn(state: bool):
        global turnPin
        turnPin.value = state
        print(f'turn {state}')
        
    def seconds_since(since):
        return r.datetime.tm_sec - since
    
    def timestamp_now():
        return r.datetime.tm_sec
    
    BUTTONS_OUT = {'⏯️'   : ConsumerControlCode.PLAY_PAUSE,
           '⏭️'   : ConsumerControlCode.SCAN_NEXT_TRACK,
           '⏮️'   : ConsumerControlCode.SCAN_PREVIOUS_TRACK,
           '+'   : ConsumerControlCode.VOLUME_INCREMENT,
           '-'   : ConsumerControlCode.VOLUME_DECREMENT,
           'HOLD': Keycode.CAPS_LOCK,
           }
    
    def key_press(key):
        print(f'key: {key}, value: {BUTTONS_OUT[key]}')
        try:
            keyboard_multimedia.send(BUTTONS_OUT[key])
        except KeyError:
            pass
        else:
            try:
                keyboard.send(BUTTONS_OUT[key])
            except KeyError:
                print('Key not known', file=stderr)
        
    def key_release(key):
        pass
                

remote_last_ACK = None
remote_last_ACK_time = timestamp_now()

remote_initialized = False

ASK = b'\xF0'
CONFIRM = b'\xF8'
PACKET_START = b'\xFD'
PACKET_END = b'\xFE'
ACK = {0: b'\xFA',
       1: b'\xFB'}

COMMANDS = {'first_ack' : b'\x80',
            'second_ack' : b'\x83',
            'buttons_84' : b'\x84',
            'buttons_85' : b'\x85',
            'psp_03': b'\x03',
            'psp_02': b'\x02'}

# name: [bitmask, linux scancode]
BUTTONS = {'⏯️'   : 0b1,
           '⏭️'   : 0b100,
           '⏮️'   : 0b1000,
           '+'   : 0b10000,
           '-'   : 0b100000,
           'HOLD': 0b10000000,
           }
remote_last_buttons = 0

def psp_keep_alive():
    global remote_last_ACK_time
    global remote_last_ACK
    global remote
    
    remote.write(ASK)
    r = remote.read(1)
    if r == ASK:
        handle_remote_ask()
        return
    assert r == CONFIRM
    remote.write(PACKET_START)
    if remote_last_ACK == ACK[1]:
        remote.write(COMMANDS['psp_02'])
        remote.write(b'\x00')
        remote.write(COMMANDS['psp_02'])
    else:
        remote.write(COMMANDS['psp_03'])
        remote.write(b'\x00')
        remote.write(COMMANDS['psp_03'])                        
    remote.write(PACKET_END)
    r = remote.read(1)
    assert r == ACK[0] or r == ACK[1], 'no ack'
    remote_last_ACK = r            
    
def handle_remote_ask():
    global remote_last_buttons
    
    remote.write(CONFIRM)  
    
    packet = b''
    while packet[-1:] != PACKET_END: 
        try:
            packet += remote.read(1)
        except TypeError:
            pass
    #packet = remote.read_until(PACKET_END)
    
    if packet[-1:] == PACKET_END:
        # success reading packet
        phase = packet[1] & 0b1
        remote.write(ACK[phase])
        
        # decode
        print(f'cmd byte: {hex(packet[1])}')
        # print(f'phase: {phase}')
        
        payload = packet[3] << 8 | packet[2]
        
        #print(f'payload: {bin(payload)[2:].zfill(16)}')
        
        if bytes([packet[1]]) in COMMANDS.values():
            # command recognized
            
            command = [k for k in COMMANDS.keys() if COMMANDS[k] == bytes([packet[1]])][0]
            print(f'detected command: {command}')
            
            if command == 'second_ack':
                remote.write(ASK)
                r = remote.read(1)
                assert r == CONFIRM
                remote.write(PACKET_START)
                remote.write(COMMANDS['psp_03'])
                remote.write(b'\x01')
                remote.write(b'\x02')
                remote.write(PACKET_END)
                r = remote.read(1)
                assert r == ACK[0] or r == ACK[1], 'no ack'
                remote_last_ACK = r
            if command == 'buttons_84' or command == 'buttons_85':
                #try:
                for button_value in BUTTONS.values():
                    button = [k for k in BUTTONS.keys() if BUTTONS[k] == button_value][0]
                    try:
                        if button_value & payload and not button_value & remote_last_buttons:
                            print(f'pressed {button}')
                            if button == 'HOLD':
                                key_press(button)
                                key_release(button)
                            else:
                                key_press(button)
                        elif not button_value & payload and button_value & remote_last_buttons:
                            print(f'released {button}')
                            if button == 'HOLD':
                                key_press(button)
                                key_release(button)
                            else:
                                key_release(button)
                    except ImportError as e:
                        print(e, file=stderr)
                
                remote_last_buttons = payload
                
                psp_keep_alive()
                remote_initialized = True
            
            # reset keep alive timer
            remote_last_ACK_time = timestamp_now()
    else:
        print('packet error', file=stderr)


def run():
    global remote_last_ACK_time, remote_initialized
    turn(False)
    sleep(.4)
    turn(True)

    while True:
        if remote.in_waiting:
            read = remote.read(1)
            if read == ASK:
                handle_remote_ask()
        else:
            # keep alive periodic timer
            if seconds_since(remote_last_ACK_time) >= 1:
                if remote_initialized:
                    try:
                        psp_keep_alive()
                        remote_last_ACK_time = timestamp_now()
                    except AssertionError:
                        remote_initialized = False

        sleep(.01)
        
#if __name__ == '__main__':
#run()
