#!/usr/bin/env python

"""
Open a shell over MAVLink.

@author: Beat Kueng (beat-kueng@gmx.net)
"""


from __future__ import print_function
import sys, select

try:
    from pymavlink import mavutil
    import serial
except:
    print("Failed to import pymavlink.")
    print("You may need to install it with 'pip install pymavlink pyserial'")
    exit(-1)
from argparse import ArgumentParser


class MavlinkSerialPort():
    '''an object that looks like a serial port, but
    transmits using mavlink SERIAL_CONTROL packets'''
    def __init__(self, portname, baudrate, devnum=0, debug=0):
        self.baudrate = 0
        self._debug = debug
        self.buf = ''
        self.port = devnum
        self.debug("Connecting with MAVLink to %s ..." % portname)
        self.mav = mavutil.mavlink_connection(portname, autoreconnect=True, baud=baudrate)
        self.mav.wait_heartbeat()
        self.debug("HEARTBEAT OK\n")
        self.debug("Locked serial device\n")

    def debug(self, s, level=1):
        '''write some debug text'''
        if self._debug >= level:
            print(s)

    def write(self, b):
        '''write some bytes'''
        self.debug("sending '%s' (0x%02x) of len %u\n" % (b, ord(b[0]), len(b)), 2)
        while len(b) > 0:
            n = len(b)
            if n > 70:
                n = 70
            buf = [ord(x) for x in b[:n]]
            buf.extend([0]*(70-len(buf)))
            self.mav.mav.serial_control_send(self.port,
                                             mavutil.mavlink.SERIAL_CONTROL_FLAG_EXCLUSIVE |
                                             mavutil.mavlink.SERIAL_CONTROL_FLAG_RESPOND,
                                             0,
                                             0,
                                             n,
                                             buf)
            b = b[n:]

    def close(self):
        self.mav.mav.serial_control_send(self.port, 0, 0, 0, 0, [0]*70)

    def _recv(self):
        '''read some bytes into self.buf'''
        m = self.mav.recv_match(condition='SERIAL_CONTROL.count!=0',
                                type='SERIAL_CONTROL', blocking=True,
                                timeout=0.03)
        if m is not None:
            if self._debug > 2:
                print(m)
            data = m.data[:m.count]
            self.buf += ''.join(str(chr(x)) for x in data)

    def read(self, n):
        '''read some bytes'''
        if len(self.buf) == 0:
            self._recv()
        if len(self.buf) > 0:
            if n > len(self.buf):
                n = len(self.buf)
            ret = self.buf[:n]
            self.buf = self.buf[n:]
            if self._debug >= 2:
                for b in ret:
                    self.debug("read 0x%x" % ord(b), 2)
            return ret
        return ''


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('port', metavar='PORT', nargs='?', default = None,
            help='Mavlink port name: serial: DEVICE[,BAUD], udp: IP:PORT, tcp: tcp:IP:PORT. Eg: \
/dev/ttyUSB0 or 0.0.0.0:14550. Auto-detect serial if not given.')
    parser.add_argument("--baudrate", "-b", dest="baudrate", type=int,
                      help="Mavlink port baud rate (default=115200)", default=115200)
    args = parser.parse_args()


    if args.port == None:
        serial_list = mavutil.auto_detect_serial(preferred_list=['*FTDI*',
            "*Arduino_Mega_2560*", "*3D_Robotics*", "*USB_to_UART*", '*PX4*', '*FMU*'])

        if len(serial_list) == 0:
            print("Error: no serial connection found")
            return

        if len(serial_list) > 1:
            print('Auto-detected serial ports are:')
            for port in serial_list:
                print(" {:}".format(port))
        print('Using port {:}'.format(serial_list[0]))
        args.port = serial_list[0].device


    print("Connecting to MAVLINK...")
    mav_serialport = MavlinkSerialPort(args.port, args.baudrate, devnum=10)

    mav_serialport.write('\n') # make sure the shell is started

    try:
        while True:
            i, o, e = select.select([sys.stdin], [], [], 0.001)
            if (i):
                data = sys.stdin.readline()

                # Erase stdin output (otherwise we have it twice)
                # FIXME: this assumes a prompt of 5 chars, and does not work in all cases
                CURSOR_UP_ONE = '\x1b[1A'
                CURSOR_RIGHT = '\x1b[5C'
                ERASE_LINE = '\x1b[2K'
                ERASE_END_LINE = '\x1b[K'
                sys.stdout.write(CURSOR_UP_ONE + CURSOR_RIGHT + ERASE_END_LINE)

                # TODO: add a command history?

                #sys.stdout.write(data)
                mav_serialport.write(data)

            data = mav_serialport.read(4096)
            if data and len(data) > 0:
                sys.stdout.write(data)
                sys.stdout.flush()

    except serial.serialutil.SerialException as e:
        print(e)

    except KeyboardInterrupt:
        mav_serialport.close()


if __name__ == '__main__':
    main()
