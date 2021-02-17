from time import sleep
from serial import Serial
import sched, time
from datetime import datetime as dt
import keyboard

scheduler = sched.scheduler(time.time, time.sleep)


remote = Serial('/dev/ttyUSB0', baudrate=4800)
remote.timeout = .30 # 30 ms is plenty to recv the packet

remote_last_ACK = None
remote_last_ACK_time = dt.now()

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

BUTTONS = {'⏯️'   : [0b1,164],
           '⏭️'   : [0b100,163],
           '⏮️'   : [0b1000,165],
           '+'   : [0b10000,115],
           '-'   : [0b100000,114],
           'HOLD': [0b10000000,113],
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
                
    packet = remote.read_until(PACKET_END)
    
    if packet[-1:] == PACKET_END:
        # success reading packet
        phase = packet[1] & 0b1
        remote.write(ACK[phase])
        
        # decode
        print(f'cmd byte: {hex(packet[1])}')
        #print(f'phase: {phase}')
        
        payload = packet[3] << 8 | packet[2]
        
        print(f'payload: {bin(payload)[2:].zfill(16)}')
        
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
                for button_value_pair in BUTTONS.values():
                    button = [k for k in BUTTONS.keys() if BUTTONS[k] == button_value_pair][0]
                    button_value = button_value_pair[0]
                    if button_value & payload and not button_value & remote_last_buttons:
                        print(f'pressed {button}')
                        if button == 'HOLD':
                            keyboard.press_and_release('caps_lock')
                        else:
                            keyboard.press(BUTTONS[button][1])
                    elif not button_value & payload and button_value & remote_last_buttons:
                        print(f'released {button}')
                        if button == 'HOLD':
                            keyboard.press_and_release('caps_lock')
                        else:
                            keyboard.release(BUTTONS[button][1])
                #except TypeError:
                    #pass
                
                remote_last_buttons = payload
                
                psp_keep_alive()
                remote_initialized = True
            
            # reset keep alive timer
            remote_last_ACK_time = dt.now()

while True:
    if remote.in_waiting:
        read = remote.read()
        if read == ASK:
            handle_remote_ask()
    else:
        # keep alive periodic timer
        if (dt.now() - remote_last_ACK_time).seconds >= 1:
            if remote_initialized:
                try:
                    psp_keep_alive()
                    remote_last_ACK_time = dt.now()
                except AssertionError:
                    remote_initialized = False

    sleep(.01)
