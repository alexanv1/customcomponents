# Python module to interface with Shenzhen Xenon ESP8266MOD WiFi smart devices
# E.g. https://wikidevi.com/wiki/Xenon_SM-PW701U
#   SKYROKU SM-PW701U Wi-Fi Plug Smart Plug
#   Wuudi SM-S0301-US - WIFI Smart Power Socket Multi Plug with 4 AC Outlets and 4 USB Charging Works with Alexa
#
# This would not exist without the protocol reverse engineering from
# https://github.com/codetheweb/tuyapi by codetheweb and blackrozes
#
# Tested with Python 2.7 and Python 3.6.1 only


import base64
from hashlib import md5
import json
import logging
import socket
import sys
import time
import colorsys
import threading
import re

try:
    #raise ImportError
    import Crypto
    from Crypto.Cipher import AES  # PyCrypto
except ImportError:
    Crypto = AES = None
    import pyaes  # https://github.com/ricmoo/pyaes


log = logging.getLogger('pytuya')
logging.basicConfig()  # TODO include function name/line numbers in log

log.info('Python %s on %s', sys.version, sys.platform)
if Crypto is None:
    log.info('Using pyaes version %r', pyaes.VERSION)
    log.info('Using pyaes from %r', pyaes.__file__)
else:
    log.info('Using PyCrypto %r', Crypto.version_info)
    log.info('Using PyCrypto from %r', Crypto.__file__)

SET = 'set'

PROTOCOL_VERSION_BYTES = b'3.1'

IS_PY2 = sys.version_info[0] == 2

class AESCipher(object):
    def __init__(self, key):
        #self.bs = 32  # 32 work fines for ON, does not work for OFF. Padding different compared to js version https://github.com/codetheweb/tuyapi/
        self.bs = 16
        self.key = key
    def encrypt(self, raw):
        if Crypto:
            raw = self._pad(raw)
            cipher = AES.new(self.key, mode=AES.MODE_ECB)
            crypted_text = cipher.encrypt(raw)
        else:
            _ = self._pad(raw)
            cipher = pyaes.blockfeeder.Encrypter(pyaes.AESModeOfOperationECB(self.key))  # no IV, auto pads to 16
            crypted_text = cipher.feed(raw)
            crypted_text += cipher.feed()  # flush final block
        crypted_text_b64 = base64.b64encode(crypted_text)
        return crypted_text_b64
    def decrypt(self, enc):
        enc = base64.b64decode(enc)
        if Crypto:
            cipher = AES.new(self.key, AES.MODE_ECB)
            raw = cipher.decrypt(enc)
            return self._unpad(raw).decode('utf-8')
        else:
            cipher = pyaes.blockfeeder.Decrypter(pyaes.AESModeOfOperationECB(self.key))  # no IV, auto pads to 16
            plain_text = cipher.feed(enc)
            plain_text += cipher.feed()  # flush final block
            return plain_text
    def _pad(self, s):
        padnum = self.bs - len(s) % self.bs
        return s + padnum * chr(padnum).encode()
    @staticmethod
    def _unpad(s):
        return s[:-ord(s[len(s)-1:])]


def bin2hex(x, pretty=False):
    if pretty:
        space = ' '
    else:
        space = ''
    if IS_PY2:
        result = ''.join('%02X%s' % (ord(y), space) for y in x)
    else:
        result = ''.join('%02X%s' % (y, space) for y in x)
    return result


def hex2bin(x):
    if IS_PY2:
        return x.decode('hex')
    else:
        return bytes.fromhex(x)

# This is intended to match requests.json payload at https://github.com/codetheweb/tuyapi
payload_dict = {
  "device": {
    "status": {
      "hexByte": "0a",
      "command": {"gwId": "", "devId": ""}
    },
    "set": {
      "hexByte": "07",
      "command": {"devId": "", "uid": "", "t": ""}
    },
    "prefix": "000055aa00000000000000",    # Next byte is command byte ("hexByte") some zero padding, then length of remaining payload, i.e. command + suffix (unclear if multiple bytes used for length, zero padding implies could be more than one byte)
    "suffix": "000000000000aa55"
  }
}

class Device(threading.Thread):
    def __init__(self, dev_id, address, local_key=None, dev_type=None, connection_timeout=10.0):
        """
        Represents a Tuya device.
        
        Args:
            dev_id (str): The device id.
            address (str): The network address.
            local_key (str, optional): The encryption key. Defaults to None.
            dev_type (str, optional): The device type.
                It will be used as key for lookups in payload_dict.
                Defaults to None.
            
        Attributes:
            port (int): The port to connect to.
        """

        self.id = dev_id
        self.address = address
        self.local_key = local_key
        self.local_key = local_key.encode('latin1')
        self.dev_type = dev_type
        self.connection_timeout = connection_timeout
        self.lock = threading.Lock()

        self.socket = None
        self.callback = None

        self.port = 6668  # default - do not expect caller to pass in

        self.state = []
    
    def subscribe(self, callback):
        """
        Connects the socket and starts the listener thread
        Passed in callback is called by the listener thread whenever data is received

        Args:
            callback(function): Callback function
        """
        self.callback = callback

        # Connect the socket
        self._connect()

        # start the listener thread
        threading.Thread.__init__(self)
        self.start()
    
    def run(self):
        """
        Runs the listener thread
        """

        log.info('%s: Socket listener thread started', self.address)

        # Request device state
        self.async_status()

        while(True):
            
            try:
                log.debug('%s: Calling recv()', self.address)
                data = self.socket.recv(1024)
            except Exception as err:
                log.info("%s: Receive error (%s), will reconnect and try again", self.address, err)
                self._connect()
                self.async_status()
                continue

            # Process the data and trigger an update if it looks like device state
            result = data[20:-8]  # hard coded offsets
            log.debug('%s: Received data: %r', self.address, result)
                
            try:
                if result.startswith(PROTOCOL_VERSION_BYTES):
                    # got an encrypted payload, happens occasionally
                    # expect resulting json to look similar to:: {"devId":"ID","dps":{"1":true,"2":0},"t":EPOCH_SECS,"s":3_DIGIT_NUM}
                    # NOTE dps.2 may or may not be present
                    result = result[len(PROTOCOL_VERSION_BYTES):]  # remove version header
                    result = result[16:]  # remove (what I'm guessing, but not confirmed is) 16-bytes of MD5 hexdigest of payload
                    cipher = AESCipher(self.local_key)
                    result = cipher.decrypt(result)
                    log.debug('%s: Decrypted data: %r', self.address, result)
                    result = json.loads(result)
                else:
                    # Find the last match of "{devID: id, dps: {state}}"
                    result = re.findall(r"{[\s\S]*?{[\s\S]*?}}", str(result))[-1]
                    log.debug('%s: Parsed data: %s', self.address, result)
                    result = json.loads(result)
            except Exception as err:
                log.info("%s: Decrypt or parse error (%s), request status update and continue", self.address, err)
                self.async_status()
                continue

            log.info('%s: Device state received: %r', self.address, result)

            # Save the state and trigger the callback
            self.state = result
            self.callback()

    def __repr__(self):
        return '%r' % ((self.id, self.address),)

    def _connect(self):
        """
        Connects to the device
        """

        self.lock.acquire()
        
        try:
            if self.socket is not None:
                self.socket.close()

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.settimeout(self.connection_timeout)
            self.socket.connect((self.address, self.port))
            self.socket.settimeout(None)        # no timeout
        except (ConnectionResetError, TimeoutError, socket.timeout) as err:
            log.warning("%s: Connect error (%s)", self.address, err)
            self.socket.close()
            self.socket = None
        except Exception as err:
            log.error("%s: Connect error (%s)", self.address, err)
            self.socket.close()
            self.socket = None

        self.lock.release()

    def _send(self, payload):
        """
        Send single buffer `payload`
        
        Args:
            payload(bytes): Data to send.
        """

        # Try 5 times since local connection to Tuya switches isn't always reliable
        MAX_RETRIES = 5
        for x in range(MAX_RETRIES):
            try:
                self.socket.send(payload)
                break
            except Exception as err:
                if x < (MAX_RETRIES - 1):
                    log.warning("%s: Send error (%s), re-connect and retry (counter=%d)", self.address, err, x)
                    self._connect()
                else:
                    log.error("%s: Send error (%s), passing exception to caller", self.address, err)
                    raise

        if not self.is_alive():        
            log.error("%s: Listening thread is not alive, will try to start it again", self.address)
            threading.Thread.__init__(self)
            self.start()

    def generate_payload(self, command, data=None):
        """
        Generate the payload to send.

        Args:
            command(str): The type of command.
                This is one of the entries from payload_dict
            data(dict, optional): The data to be send.
                This is what will be passed via the 'dps' entry
        """
        json_data = payload_dict[self.dev_type][command]['command']

        if 'gwId' in json_data:
            json_data['gwId'] = self.id
        if 'devId' in json_data:
            json_data['devId'] = self.id
        if 'uid' in json_data:
            json_data['uid'] = self.id  # still use id, no seperate uid
        if 't' in json_data:
            json_data['t'] = str(int(time.time()))

        if data is not None:
            json_data['dps'] = data

        # Create byte buffer from hex data
        json_payload = json.dumps(json_data)
        json_payload = json_payload.replace(' ', '')  # if spaces are not removed device does not respond!
        json_payload = json_payload.encode('utf-8')
        log.debug('%s: Generated JSON payload=%r', self.address, json_payload)

        if command == SET:
            # need to encrypt
            self.cipher = AESCipher(self.local_key)  # expect to connect and then disconnect to set new
            json_payload = self.cipher.encrypt(json_payload)
            preMd5String = b'data=' + json_payload + b'||lpv=' + PROTOCOL_VERSION_BYTES + b'||' + self.local_key
            m = md5()
            m.update(preMd5String)
            hexdigest = m.hexdigest()
            json_payload = PROTOCOL_VERSION_BYTES + hexdigest[8:][:16].encode('latin1') + json_payload
            self.cipher = None  # expect to connect and then disconnect to set new


        postfix_payload = hex2bin(bin2hex(json_payload) + payload_dict[self.dev_type]['suffix'])
        assert len(postfix_payload) <= 0xff
        postfix_payload_hex_len = '%x' % len(postfix_payload)  # TODO this assumes a single byte 0-255 (0x00-0xff)
        buffer = hex2bin( payload_dict[self.dev_type]['prefix'] + 
                          payload_dict[self.dev_type][command]['hexByte'] + 
                          '000000' +
                          postfix_payload_hex_len ) + postfix_payload
        return buffer
    
    def async_status(self):
        """
        Starts an async status update. When device returns status, the callback will be triggered
        """

        log.debug('%s: async_status() called', self.address)

        # send status request
        payload = self.generate_payload('status')
        self._send(payload)

    def status(self):
        """
        Returns our status
        """
        return self.state

    def set_status(self, on, switch='1'):
        """
        Set status of the device to 'on' or 'off'.
        
        Args:
            on(bool):  True for 'on', False for 'off'.
            switch(int): The switch to set
        """

        if isinstance(switch, int):
            switch = str(switch)  # index and payload is a string
        payload = self.generate_payload(SET, {switch:on})

        self._send(payload)
        log.debug('%s: set_status completed', self.address)

    def set_diffuser_mist_mode(self, mode, switch='1'):
        """
        Set diffuser mist mode (always turns the device 'on' as well)
        
        Args:
            switch(int): The switch to set
            mode(string): The mode to set ('continuous', 'intermittent' or 'off')
        """
        # open device, send request, then close connection
        if isinstance(switch, int):
            switch = str(switch)  # index and payload is a string
        if mode == 'continuous':
            payload = self.generate_payload(SET, {switch:True, '101':'1'})
        elif mode == 'intermittent':
            payload = self.generate_payload(SET, {switch:True, '101':'2'})
        else:
            payload = self.generate_payload(SET, {switch:True, '101':'3'})

        self._send(payload)
        log.debug('%s: set_diffuser_mist_mode completed', self.address)

    def set_timer(self, num_secs):
        """
        Set a timer.
        
        Args:
            num_secs(int): Number of seconds
        """
        # FIXME / TODO support schemas? Accept timer id number as parameter?

        # Dumb heuristic; Query status, pick last device id as that is probably the timer
        status = self.status()
        devices = status['dps']
        devices_numbers = list(devices.keys())
        devices_numbers.sort()
        dps_id = devices_numbers[-1]

        payload = self.generate_payload(SET, {dps_id:num_secs})

        self._send(payload)
        log.debug('%s: set_timer completed', self.address)

class OutletDevice(Device):
    def __init__(self, dev_id, address, local_key=None):
        dev_type = 'device'
        super(OutletDevice, self).__init__(dev_id, address, local_key, dev_type)

class BulbDevice(Device):
    def __init__(self, dev_id, address, local_key=None):
        dev_type = 'device'
        super(BulbDevice, self).__init__(dev_id, address, local_key, dev_type)

    def set_colour(self, r, g, b, brightness):
        """
        Set colour of an rgb bulb.

        Args:
            r(int): Value for the colour red as int from 0-255.
            g(int): Value for the colour green as int from 0-255.
            b(int): Value for the colour blue as int from 0-255.
        """
        if not 0 <= r <= 255:
            raise ValueError("The value for red needs to be between 0 and 255.")
        if not 0 <= g <= 255:
            raise ValueError("The value for green needs to be between 0 and 255.")
        if not 0 <= b <= 255:
            raise ValueError("The value for blue needs to be between 0 and 255.")

        # pre-multiply by brighness value
        r = r * brightness / 255
        g = g * brightness / 255
        b = b * brightness / 255
        
        rgb = [r,g,b]
        hsv = colorsys.rgb_to_hsv(rgb[0]/255, rgb[1]/255, rgb[2]/255)

        hexvalue = ""
        for value in rgb:
            temp = str(hex(int(value))).replace("0x","")
            if len(temp) == 1:
                temp = "0" + temp
            hexvalue = hexvalue + temp

        hsvarray = [int(hsv[0] * 360), int(hsv[1] * 255), int(hsv[2] * 255)]
        hexvalue_hsv = ""
        for value in hsvarray:
            temp = str(hex(int(value))).replace("0x","")
            if len(temp) == 1:
                temp = "0" + temp
            hexvalue_hsv = hexvalue_hsv + temp
        if len(hexvalue_hsv) == 7:
            hexvalue = hexvalue + "0" + hexvalue_hsv
        else:
            hexvalue = hexvalue + "00" + hexvalue_hsv

        payload = self.generate_payload(SET, {'1': True, '2': 'colour', '3': brightness, '5': hexvalue})
        
        self._send(payload)
        log.debug('%s: set_colour completed', self.address)

    def set_white(self, brightness, colourtemp):
        """
        Set white coloured theme of an rgb bulb.

        Args:
            brightness(int): Value for the brightness (25-255).
            colourtemp(int): Value for the colour temperature (0-255).
        """
        if not 25 <= brightness <= 255:
            raise ValueError("The brightness needs to be between 25 and 255.")
        if not 0 <= colourtemp <= 255:
            raise ValueError("The colour temperature needs to be between 0 and 255.")

        payload = self.generate_payload(SET, {'1': True, '2': 'white', '3': brightness, '4': colourtemp})

        self._send(payload)
        log.debug('%s: set_white completed', self.address)

    def set_brightness(self, brightness):
        """
        Set brightness of an rgb bulb.

        Args:
            brightness(int): Value for the brightness (25-255).
        """
        if not 25 <= brightness <= 255:
            raise ValueError("The brightness needs to be between 25 and 255.")

        payload = self.generate_payload(SET, {'1': True, '3': brightness})
        
        self._send(payload)
        log.debug('%s: set_brightness completed', self.address)
