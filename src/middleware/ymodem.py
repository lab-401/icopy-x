##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com/quantum-x/
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""YMODEM protocol implementation — replaces ymodem.so.

Exports:
    Constants: SOH, STX, EOT, ACK, NAK, CAN, CRC
    Classes: TaskState, SendTask, ReceiveTask, YModemCommon, YModemSTM32
    Functions: bytesToHexString(bs), call(v1, v2, v3)

Source: docs/V1090_MODULE_AUDIT.txt (lines 1076-1142),
        decompiled/ymodem_ghidra_raw.txt (40045 lines),
        archive/lib_transliterated/ymodem.py,
        docs/v1090_strings/ymodem_strings.txt

Error strings (from Ghidra @ 0x0003b094-0x0003bc80):
    "wait_for_header() -> Expected 0x01(SOH)/0x02(STX)/0x18(CAN), but got "
    "send error, expected CRC or CAN, but got "
    "send error, expected ACK or CAN, but got "
    "send error: error_count reached %d aborting"
    "send error: NAK received %d , aborting"
    "recv_file() -> Expected 0x01(SOH)/0x02(STX)/0x18(CAN), but got "
    "EOT wasnt ACKd, aborting transfer"
    "SOH wasnt ACK, aborting transfer"
    "Expected 0x04(EOT), but got "
    "ACK wasnt CRCd"
    "WAIT_FOR_EOT"

Dependencies: hmi_driver, math, os, time, update

Original Cython source path:
    lib/ymodem.so (287KB, ARM ELF, Cython 0.29.21)
    MD5: 3482961d9fe779429ace4d55ee32d48d
"""

import logging
import math
import os
import time

logger = logging.getLogger(__name__)

try:
    import hmi_driver
except ImportError:
    hmi_driver = None

# ═══════════════════════════════════════════════════════════════════════════
# Protocol constants — EXACT from module audit + Ghidra verification
# ═══════════════════════════════════════════════════════════════════════════

SOH = b'\x01'   # Start of 128-byte data packet
STX = b'\x02'   # Start of 1024-byte data packet
EOT = b'\x04'   # End of transmission
ACK = b'\x06'   # Acknowledge
NAK = b'\x15'   # Negative acknowledge
CAN = b'\x18'   # Cancel
CRC = b'C'      # CRC mode request


# ═══════════════════════════════════════════════════════════════════════════
# TaskState — transfer state constants
# QEMU-verified: PREPARED=0, RUNNING=1, FINISHED=2, ABORTED=-1, ERROR=-99
# ═══════════════════════════════════════════════════════════════════════════

class TaskState:
    PREPARED = 0
    RUNNING = 1
    FINISHED = 2
    ABORTED = -1
    ERROR = -99


# ═══════════════════════════════════════════════════════════════════════════
# SendTask — data tracking for send operations
# Source: V1090_MODULE_AUDIT.txt lines 1107-1116
# ═══════════════════════════════════════════════════════════════════════════

class SendTask:
    def __init__(self):
        self._task_name = ""
        self._task_size = 0
        self._sent_packets = 0
        self._valid_sent_packets = 0
        self._missing_sent_packets = 0
        self._valid_sent_bytes = 0

    def set_task_name(self, data_name):
        self._task_name = data_name

    def get_task_name(self):
        return self._task_name

    def set_task_size(self, data_size):
        self._task_size = data_size

    def get_task_size(self):
        return self._task_size

    def inc_sent_packets(self):
        self._sent_packets += 1

    def inc_valid_sent_packets(self):
        self._valid_sent_packets += 1

    def get_valid_sent_packets(self):
        return self._valid_sent_packets

    def inc_missing_sent_packets(self):
        self._missing_sent_packets += 1

    def add_valid_sent_bytes(self, this_valid_sent_bytes):
        self._valid_sent_bytes += this_valid_sent_bytes

    def get_valid_sent_bytes(self):
        return self._valid_sent_bytes


# ═══════════════════════════════════════════════════════════════════════════
# ReceiveTask — data tracking for receive operations
# Source: V1090_MODULE_AUDIT.txt lines 1093-1106
# ═══════════════════════════════════════════════════════════════════════════

class ReceiveTask:
    def __init__(self):
        self._task_name = ""
        self._task_size = 0
        self._received_packets = 0
        self._valid_received_packets = 0
        self._missing_received_packets = 0
        self._valid_received_bytes = 0
        self._last_valid_packet_size = 0

    def set_task_name(self, data_name):
        self._task_name = data_name

    def get_task_name(self):
        return self._task_name

    def set_task_size(self, data_size):
        self._task_size = data_size

    def get_task_size(self):
        return self._task_size

    def inc_received_packets(self):
        self._received_packets += 1

    def get_task_packets(self):
        return self._received_packets

    def inc_valid_received_packets(self):
        self._valid_received_packets += 1

    def get_valid_received_packets(self):
        return self._valid_received_packets

    def inc_missing_received_packets(self):
        self._missing_received_packets += 1

    def add_valid_received_bytes(self, this_valid_received_bytes):
        self._valid_received_bytes += this_valid_received_bytes
        self._last_valid_packet_size = this_valid_received_bytes

    def get_valid_received_bytes(self):
        return self._valid_received_bytes

    def get_last_valid_packet_size(self):
        return self._last_valid_packet_size


# ═══════════════════════════════════════════════════════════════════════════
# YModemCommon — full YMODEM protocol implementation
# Source: V1090_MODULE_AUDIT.txt lines 1119-1132
# Ghidra functions at 0x0002c1c4 (send), 0x0002fd38 (send_file),
#   0x000364ac (recv_file), 0x000234d0 (wait_for_header),
#   0x00023d44 (wait_for_next), 0x0002b660 (wait_for_eot)
# ═══════════════════════════════════════════════════════════════════════════

class YModemCommon:
    """Common YMODEM protocol implementation.

    Args:
        getc: callable — read bytes from serial (returns bytes or b'')
        putc: callable — write bytes to serial
        header_pad: padding byte for headers (default 0x00)
        data_pad: padding byte for data (default 0x1a / SUB)
    """

    def __init__(self, getc, putc, header_pad=b'\x00', data_pad=b'\x1a'):
        self.getc = getc
        self.putc = putc
        self.header_pad = header_pad
        self.data_pad = data_pad

    # -------------------------------------------------------------------
    # CRC-16/XMODEM — polynomial 0x1021, init 0
    # Ghidra: __pyx_pw_6ymodem_12YModemCommon_25calc_crc_direct @ 0x0002ad60
    # -------------------------------------------------------------------

    @staticmethod
    def calc_crc_direct(data):
        """Calculate CRC-16/XMODEM checksum over data bytes."""
        crc = 0
        for byte in data:
            if isinstance(byte, int):
                crc ^= byte << 8
            else:
                crc ^= ord(byte) << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc <<= 1
                crc &= 0xFFFF
        return crc

    # -------------------------------------------------------------------
    # Packet header builders
    # Ghidra: _make_data_packet_header @ 0x00022f94 (via string ref)
    #         _make_edge_packet_header @ 0x00022f94
    # -------------------------------------------------------------------

    def _make_data_packet_header(self, packet_size, sequence):
        """Build header for a data packet: [SOH/STX][seq][~seq]."""
        if packet_size == 128:
            header = SOH
        elif packet_size == 1024:
            header = STX
        else:
            raise ValueError("Invalid packet size: %d" % packet_size)
        return header + bytes([sequence & 0xFF, 0xFF - (sequence & 0xFF)])

    def _make_edge_packet_header(self):
        """Build header for filename/end-of-batch packet: [SOH][0x00][0xFF]."""
        return SOH + b'\x00\xff'

    # -------------------------------------------------------------------
    # Checksum methods
    # Ghidra: _make_send_checksum @ 0x00033684
    #         _verify_recv_checksum @ 0x0003aee0
    # -------------------------------------------------------------------

    def _make_send_checksum(self, data):
        """Compute CRC-16 and return as 2-byte big-endian bytes."""
        crc = self.calc_crc_direct(data)
        return bytes([crc >> 8, crc & 0xFF])

    def _verify_recv_checksum(self, data):
        """Verify CRC-16 on received data (last 2 bytes are the CRC).

        Returns True if valid, False otherwise.
        """
        if len(data) < 3:
            return False
        payload = data[:-2]
        recv_crc = (data[-2] << 8) | data[-1]
        return self.calc_crc_direct(payload) == recv_crc

    # -------------------------------------------------------------------
    # abort — send CAN bytes to cancel transfer
    # Ghidra: __pyx_pw_6ymodem_12YModemCommon_3abort @ 0x00024778
    # -------------------------------------------------------------------

    def abort(self, count=2):
        """Send CAN bytes to abort the transfer."""
        for _ in range(count):
            self.putc(CAN)

    # -------------------------------------------------------------------
    # wait_for_header — wait for SOH/STX/CAN from receiver
    # Ghidra: __pyx_pw_6ymodem_12YModemCommon_11wait_for_header @ 0x000234d0
    # Error: "wait_for_header() -> Expected 0x01(SOH)/0x02(STX)/0x18(CAN), but got "
    # -------------------------------------------------------------------

    def wait_for_header(self):
        """Wait for a packet header byte (SOH, STX, or CAN).

        Returns:
            SOH, STX if header received; None if cancelled or timeout.
        """
        cancel_count = 0
        while True:
            c = self.getc()
            if not c:
                continue
            if c == SOH or c == STX:
                return c
            elif c == CAN:
                cancel_count += 1
                if cancel_count >= 2:
                    return None
            else:
                if isinstance(c, (bytes, bytearray)):
                    val = c[0] if c else 0
                else:
                    val = ord(c)
                logger.debug(
                    "wait_for_header() -> Expected 0x01(SOH)/0x02(STX)/"
                    "0x18(CAN), but got %s", hex(val)
                )

    # -------------------------------------------------------------------
    # wait_for_next — wait for a specific byte
    # Ghidra: __pyx_pw_6ymodem_12YModemCommon_7wait_for_next @ 0x00023d44
    # -------------------------------------------------------------------

    def wait_for_next(self, ch):
        """Wait until the given byte is received.

        Args:
            ch: expected byte (bytes object, length 1)

        Returns:
            True if received, False on timeout/cancel.
        """
        cancel_count = 0
        while True:
            c = self.getc()
            if not c:
                continue
            if c == ch:
                return True
            if c == CAN:
                cancel_count += 1
                if cancel_count >= 2:
                    return False

    # -------------------------------------------------------------------
    # wait_for_eot — wait for EOT (end of transmission)
    # Ghidra: __pyx_pw_6ymodem_12YModemCommon_13wait_for_eot @ 0x0002b660
    # Error: "Expected 0x04(EOT), but got "
    # State: WAIT_FOR_EOT
    # -------------------------------------------------------------------

    def wait_for_eot(self):
        """Wait for EOT from sender.

        Returns:
            True if EOT received, False on timeout/cancel.
        """
        while True:
            c = self.getc()
            if not c:
                continue
            if c == EOT:
                return True
            if c == CAN:
                return False
            if isinstance(c, (bytes, bytearray)):
                val = c[0] if c else 0
            else:
                val = ord(c)
            logger.debug("Expected 0x04(EOT), but got %s", hex(val))

    # -------------------------------------------------------------------
    # send — send data stream via YMODEM protocol
    # Ghidra: __pyx_pw_6ymodem_12YModemCommon_9send @ 0x0002c1c4
    #         __pyx_gb_6ymodem_12YModemCommon_4send_2generator @ 0x0001fa44
    # Errors: "send error, expected CRC or CAN, but got "
    #         "send error, expected ACK or CAN, but got "
    #         "send error: error_count reached %d aborting"
    #         "send error: NAK received %d , aborting"
    #         "EOT wasnt ACKd, aborting transfer"
    #         "SOH wasnt ACK, aborting transfer"
    #         "ACK wasnt CRCd"
    # -------------------------------------------------------------------

    def send(self, data_stream, data_name, data_size, retry=20, callback=None):
        """Send a data stream using the YMODEM protocol.

        Args:
            data_stream: file-like object with read() method
            data_name: filename to send in header packet
            data_size: total size in bytes
            retry: max retries per packet (default 20)
            callback: optional progress callback(task: SendTask)

        Returns:
            True on success, False on failure.
        """
        # -- Wait for receiver's initial 'C' (CRC mode request) --
        error_count = 0
        crc_mode = False
        while not crc_mode:
            c = self.getc()
            if not c:
                error_count += 1
                if error_count >= retry:
                    logger.error("send error: error_count reached %d aborting",
                                 error_count)
                    self.abort()
                    return False
                continue
            if c == CRC:
                crc_mode = True
            elif c == CAN:
                logger.error("send error: cancelled by receiver")
                return False
            else:
                error_count += 1

        task = SendTask()
        task.set_task_name(data_name)
        task.set_task_size(data_size)

        # -- Send filename packet (sequence 0) --
        if isinstance(data_name, str):
            data_name_bytes = data_name.encode('latin-1')
        else:
            data_name_bytes = data_name

        name_data = data_name_bytes + b'\x00' + str(data_size).encode() + b'\x00'
        packet_size = 128
        # Pad to packet_size
        if len(name_data) < packet_size:
            name_data = name_data + self.header_pad * (packet_size - len(name_data))

        header = self._make_edge_packet_header()
        checksum = self._make_send_checksum(name_data)
        self.putc(header + name_data + checksum)

        # Wait for ACK
        error_count = 0
        while True:
            c = self.getc()
            if not c:
                error_count += 1
                if error_count >= retry:
                    logger.error("SOH wasnt ACK, aborting transfer")
                    self.abort()
                    return False
                continue
            if c == ACK:
                break
            elif c == CAN:
                logger.error("send error: cancelled by receiver")
                return False
            elif c == NAK:
                error_count += 1
                if error_count >= retry:
                    logger.error("send error: NAK received %d , aborting",
                                 error_count)
                    self.abort()
                    return False
                # Resend filename packet
                self.putc(header + name_data + checksum)
            else:
                if isinstance(c, (bytes, bytearray)):
                    val = c[0] if c else 0
                else:
                    val = ord(c)
                logger.debug("send error, expected ACK or CAN, but got %s",
                             hex(val))
                error_count += 1

        # Wait for 'C' after ACK (receiver ready for data)
        error_count = 0
        while True:
            c = self.getc()
            if not c:
                error_count += 1
                if error_count >= retry:
                    logger.error("ACK wasnt CRCd")
                    self.abort()
                    return False
                continue
            if c == CRC:
                break
            elif c == CAN:
                return False
            else:
                error_count += 1

        # -- Send data packets --
        sequence = 1
        sent_bytes = 0

        while sent_bytes < data_size:
            chunk = data_stream.read(packet_size)
            if not chunk:
                break

            actual_len = len(chunk)
            # Pad to packet_size
            if len(chunk) < packet_size:
                chunk = chunk + self.data_pad * (packet_size - len(chunk))

            pkt_header = self._make_data_packet_header(packet_size,
                                                        sequence & 0xFF)
            pkt_checksum = self._make_send_checksum(chunk)
            packet = pkt_header + chunk + pkt_checksum

            # Send with retry
            error_count = 0
            nak_count = 0
            success = False

            while not success:
                task.inc_sent_packets()
                self.putc(packet)

                # Wait for ACK
                c = self.getc()
                if not c:
                    error_count += 1
                    if error_count >= retry:
                        logger.error(
                            "send error: error_count reached %d aborting",
                            error_count)
                        self.abort()
                        return False
                    continue

                if c == ACK:
                    success = True
                    task.inc_valid_sent_packets()
                    task.add_valid_sent_bytes(actual_len)
                elif c == NAK:
                    nak_count += 1
                    error_count += 1
                    if nak_count >= retry:
                        logger.error(
                            "send error: NAK received %d , aborting",
                            nak_count)
                        self.abort()
                        return False
                elif c == CAN:
                    logger.error("send error: cancelled by receiver")
                    self.abort()
                    return False
                else:
                    if isinstance(c, (bytes, bytearray)):
                        val = c[0] if c else 0
                    else:
                        val = ord(c)
                    logger.debug(
                        "send error, expected ACK or CAN, but got %s",
                        hex(val))
                    error_count += 1
                    if error_count >= retry:
                        logger.error(
                            "send error: error_count reached %d aborting",
                            error_count)
                        self.abort()
                        return False

            sent_bytes += actual_len
            sequence += 1

            if callback:
                callback(task)

        # -- Send EOT --
        error_count = 0
        while True:
            self.putc(EOT)
            c = self.getc()
            if not c:
                error_count += 1
                if error_count >= retry:
                    logger.error("EOT wasnt ACKd, aborting transfer")
                    self.abort()
                    return False
                continue
            if c == ACK:
                break
            elif c == NAK:
                # Per YMODEM spec, first EOT may be NAK'd — retry
                error_count += 1
                if error_count >= retry:
                    logger.error("EOT wasnt ACKd, aborting transfer")
                    self.abort()
                    return False
            elif c == CAN:
                return False
            else:
                error_count += 1

        # -- Send end-of-batch (null filename packet) --
        null_data = self.header_pad * packet_size
        header = self._make_edge_packet_header()
        checksum = self._make_send_checksum(null_data)
        self.putc(header + null_data + checksum)

        # Wait for final ACK
        error_count = 0
        while True:
            c = self.getc()
            if not c:
                error_count += 1
                if error_count >= retry:
                    break  # Best-effort — transfer complete
                continue
            if c == ACK:
                break
            else:
                error_count += 1
                if error_count >= retry:
                    break

        return True

    # -------------------------------------------------------------------
    # send_file — file wrapper around send()
    # Ghidra: __pyx_pw_6ymodem_12YModemCommon_5send_file @ 0x0002fd38
    # -------------------------------------------------------------------

    def send_file(self, file_path, retry=20, callback=None):
        """Send a file using the YMODEM protocol.

        Args:
            file_path: path to the file to send
            retry: max retries per packet (default 20)
            callback: optional progress callback(task: SendTask)

        Returns:
            True on success, False on failure.
        """
        if not os.path.exists(file_path):
            return False

        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)

        with open(file_path, 'rb') as f:
            return self.send(f, file_name, file_size, retry=retry,
                             callback=callback)

    # -------------------------------------------------------------------
    # recv_file — receive a file via YMODEM
    # Ghidra: __pyx_pw_6ymodem_12YModemCommon_15recv_file @ 0x000364ac
    # Error: "recv_file() -> Expected 0x01(SOH)/0x02(STX)/0x18(CAN), but got "
    # States: FIRST_PACKET_RECEIVED, IS_FIRST_PACKET, WAIT_FOR_END_PACKET
    # -------------------------------------------------------------------

    def recv_file(self, root_path, callback=None):
        """Receive a file using the YMODEM protocol.

        Args:
            root_path: directory to save received file
            callback: optional progress callback(task: ReceiveTask)

        Returns:
            Received filename on success, None on failure.
        """
        task = ReceiveTask()

        # Send 'C' to request CRC mode
        self.putc(CRC)

        # Wait for filename packet header
        header = self.wait_for_header()
        if header is None:
            return None

        # Determine packet size from header
        if header == SOH:
            packet_size = 128
        elif header == STX:
            packet_size = 1024
        else:
            return None

        # Read sequence + complement + data + CRC
        # Sequence bytes (2)
        seq_data = b''
        for _ in range(2):
            c = self.getc()
            if c:
                seq_data += c

        # Payload + CRC (packet_size + 2)
        payload_crc = b''
        for _ in range(packet_size + 2):
            c = self.getc()
            if c:
                payload_crc += c

        if len(payload_crc) < packet_size + 2:
            return None

        payload = payload_crc[:packet_size]
        if not self._verify_recv_checksum(payload_crc):
            self.putc(NAK)
            return None

        # Parse filename and size from payload
        # Format: filename\0filesize\0
        null_pos = payload.index(b'\x00') if b'\x00' in payload else -1
        if null_pos < 0:
            self.putc(NAK)
            return None

        file_name = payload[:null_pos].decode('latin-1')
        if not file_name:
            # Null filename = end of batch
            self.putc(ACK)
            return None

        remaining = payload[null_pos + 1:]
        size_end = remaining.index(b'\x00') if b'\x00' in remaining else len(remaining)
        try:
            file_size = int(remaining[:size_end].decode('latin-1'))
        except (ValueError, UnicodeDecodeError):
            file_size = 0

        task.set_task_name(file_name)
        task.set_task_size(file_size)

        # ACK filename packet
        self.putc(ACK)
        # Send 'C' to start data transfer
        self.putc(CRC)

        # Receive data packets
        file_path = os.path.join(root_path, file_name)
        received_bytes = 0
        sequence = 1

        with open(file_path, 'wb') as f:
            while True:
                # Read next byte — could be SOH/STX (data) or EOT (end)
                c = b''
                while not c:
                    c = self.getc()

                if c == EOT:
                    # YMODEM: NAK first EOT, ACK second
                    self.putc(NAK)
                    c2 = b''
                    while not c2:
                        c2 = self.getc()
                    if c2 == EOT:
                        self.putc(ACK)
                    break

                if c == CAN:
                    break

                if c == SOH:
                    pkt_size = 128
                elif c == STX:
                    pkt_size = 1024
                else:
                    if isinstance(c, (bytes, bytearray)):
                        val = c[0] if c else 0
                    else:
                        val = ord(c)
                    logger.debug(
                        "recv_file() -> Expected 0x01(SOH)/0x02(STX)/"
                        "0x18(CAN), but got %s", hex(val))
                    continue

                # Read sequence + complement
                seq_data = b''
                for _ in range(2):
                    b = self.getc()
                    if b:
                        seq_data += b

                # Read data + CRC
                payload_crc = b''
                for _ in range(pkt_size + 2):
                    b = self.getc()
                    if b:
                        payload_crc += b

                if len(payload_crc) < pkt_size + 2:
                    self.putc(NAK)
                    task.inc_missing_received_packets()
                    continue

                task.inc_received_packets()

                if not self._verify_recv_checksum(payload_crc):
                    self.putc(NAK)
                    task.inc_missing_received_packets()
                    continue

                data = payload_crc[:pkt_size]

                # Write data (trim to file_size on last packet)
                write_size = min(len(data), file_size - received_bytes)
                if write_size > 0:
                    f.write(data[:write_size])
                    received_bytes += write_size

                task.inc_valid_received_packets()
                task.add_valid_received_bytes(write_size)

                self.putc(ACK)
                sequence += 1

                if callback:
                    callback(task)

        # Receive end-of-batch (null filename) — send 'C' then ACK
        self.putc(CRC)
        # Wait for null filename packet header
        c = b''
        while not c:
            c = self.getc()
        if c == SOH or c == STX:
            # Read and discard the null filename packet
            pkt_size = 128 if c == SOH else 1024
            for _ in range(2 + pkt_size + 2):  # seq + data + crc
                self.getc()
        self.putc(ACK)

        return file_name


# ═══════════════════════════════════════════════════════════════════════════
# YModemSTM32 — STM32/GD32 bootloader YMODEM variant
# Source: V1090_MODULE_AUDIT.txt lines 1133-1140
# Standalone class (does NOT inherit YModemCommon per module audit)
# Focused on sending firmware to STM32/GD32 bootloaders.
# Ghidra: __pyx_pw_6ymodem_11YModemSTM32_5send @ 0x00025e8c
# ═══════════════════════════════════════════════════════════════════════════

class YModemSTM32:
    """YMODEM variant for STM32/GD32 bootloader firmware updates.

    Args:
        getc: callable — read bytes from serial
        putc: callable — write bytes to serial
        mode: protocol mode (default 'ymodem')
        header_pad: padding for headers (default 0x00)
        pad: padding for data (default 0x1a)
    """

    def __init__(self, getc, putc, mode='ymodem', header_pad=b'\x00',
                 pad=b'\x1a'):
        self.getc = getc
        self.putc = putc
        self.mode = mode
        self.header_pad = header_pad
        self.pad = pad

    # -------------------------------------------------------------------
    # CRC calculation — instance method with seed for incremental computation
    # Ghidra: __pyx_pw_6ymodem_11YModemSTM32_13calc_crc @ 0x00020bd4
    # -------------------------------------------------------------------

    def calc_crc(self, data, crc=0):
        """Calculate CRC-16/XMODEM with optional seed for incremental use."""
        for byte in data:
            if isinstance(byte, int):
                crc ^= byte << 8
            else:
                crc ^= ord(byte) << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc <<= 1
                crc &= 0xFFFF
        return crc

    # -------------------------------------------------------------------
    # Packet header builder
    # Ghidra: __pyx_pw_6ymodem_11YModemSTM32_7_make_send_header @ 0x00034750
    # Confirmed: checks packet_size == 128 (0x80) or 1024 (0x400)
    # -------------------------------------------------------------------

    def _make_send_header(self, packet_size, sequence):
        """Build packet header: [SOH/STX][seq][~seq]."""
        if packet_size == 128:
            header = SOH
        elif packet_size == 1024:
            header = STX
        else:
            raise ValueError(packet_size)
        return header + bytes([sequence & 0xFF, 0xFF - (sequence & 0xFF)])

    # -------------------------------------------------------------------
    # Checksum methods
    # Ghidra: __pyx_pw_6ymodem_11YModemSTM32_9_make_send_checksum @ 0x00032fd0
    #         __pyx_pw_6ymodem_11YModemSTM32_11_verify_recv_checksum @ 0x00021e00
    # -------------------------------------------------------------------

    def _make_send_checksum(self, data):
        """Compute CRC-16 and return as 2-byte big-endian."""
        crc = self.calc_crc(data)
        return bytes([crc >> 8, crc & 0xFF])

    def _verify_recv_checksum(self, data):
        """Verify CRC-16 on received data (last 2 bytes are CRC)."""
        if len(data) < 3:
            return False
        payload = data[:-2]
        recv_crc = (data[-2] << 8) | data[-1]
        return self.calc_crc(payload) == recv_crc

    # -------------------------------------------------------------------
    # abort
    # Ghidra: __pyx_pw_6ymodem_11YModemSTM32_3abort @ 0x00024fd8
    # -------------------------------------------------------------------

    def abort(self, count=2):
        """Send CAN bytes to abort the transfer."""
        for _ in range(count):
            self.putc(CAN)

    # -------------------------------------------------------------------
    # send — STM32 bootloader firmware transfer
    # Ghidra: __pyx_pw_6ymodem_11YModemSTM32_5send @ 0x00025e8c
    # -------------------------------------------------------------------

    def send(self, file_stream, file_name, file_size, retry=20,
             callback=None):
        """Send firmware to STM32/GD32 bootloader via YMODEM.

        Args:
            file_stream: file-like object with read() method
            file_name: firmware filename
            file_size: firmware size in bytes
            retry: max retries (default 20)
            callback: optional progress callback(task: SendTask)

        Returns:
            True on success, False on failure.
        """
        packet_size = 128

        # Wait for bootloader's 'C' (CRC mode request)
        error_count = 0
        crc_mode = False
        while not crc_mode:
            c = self.getc()
            if not c:
                error_count += 1
                if error_count >= retry:
                    logger.error("send error: error_count reached %d aborting",
                                 error_count)
                    self.abort()
                    return False
                continue
            if c == CRC:
                crc_mode = True
            elif c == CAN:
                return False
            else:
                error_count += 1

        task = SendTask()
        task.set_task_name(file_name)
        task.set_task_size(file_size)

        # -- Filename packet (sequence 0) --
        if isinstance(file_name, str):
            name_bytes = file_name.encode('latin-1')
        else:
            name_bytes = file_name

        name_data = name_bytes + b'\x00' + str(file_size).encode() + b'\x00'
        if len(name_data) < packet_size:
            name_data = name_data + self.header_pad * (packet_size -
                                                        len(name_data))

        header = self._make_send_header(packet_size, 0)
        checksum = self._make_send_checksum(name_data)
        self.putc(header + name_data + checksum)

        # Wait for ACK
        error_count = 0
        while True:
            c = self.getc()
            if not c:
                error_count += 1
                if error_count >= retry:
                    logger.error("SOH wasnt ACK, aborting transfer")
                    self.abort()
                    return False
                continue
            if c == ACK:
                break
            elif c == CAN:
                return False
            elif c == NAK:
                error_count += 1
                if error_count >= retry:
                    logger.error("send error: NAK received %d , aborting",
                                 error_count)
                    self.abort()
                    return False
                self.putc(header + name_data + checksum)
            else:
                error_count += 1

        # Wait for 'C' after ACK
        error_count = 0
        while True:
            c = self.getc()
            if not c:
                error_count += 1
                if error_count >= retry:
                    logger.error("ACK wasnt CRCd")
                    self.abort()
                    return False
                continue
            if c == CRC:
                break
            elif c == CAN:
                return False
            else:
                error_count += 1

        # -- Data packets --
        sequence = 1
        sent_bytes = 0

        while sent_bytes < file_size:
            chunk = file_stream.read(packet_size)
            if not chunk:
                break

            actual_len = len(chunk)
            if len(chunk) < packet_size:
                chunk = chunk + self.pad * (packet_size - len(chunk))

            pkt_header = self._make_send_header(packet_size, sequence & 0xFF)
            pkt_checksum = self._make_send_checksum(chunk)
            packet = pkt_header + chunk + pkt_checksum

            error_count = 0
            nak_count = 0
            success = False

            while not success:
                task.inc_sent_packets()
                self.putc(packet)

                c = self.getc()
                if not c:
                    error_count += 1
                    if error_count >= retry:
                        logger.error(
                            "send error: error_count reached %d aborting",
                            error_count)
                        self.abort()
                        return False
                    continue

                if c == ACK:
                    success = True
                    task.inc_valid_sent_packets()
                    task.add_valid_sent_bytes(actual_len)
                elif c == NAK:
                    nak_count += 1
                    error_count += 1
                    if nak_count >= retry:
                        logger.error(
                            "send error: NAK received %d , aborting",
                            nak_count)
                        self.abort()
                        return False
                elif c == CAN:
                    self.abort()
                    return False
                else:
                    if isinstance(c, (bytes, bytearray)):
                        val = c[0] if c else 0
                    else:
                        val = ord(c)
                    logger.debug(
                        "send error, expected ACK or CAN, but got %s",
                        hex(val))
                    error_count += 1
                    if error_count >= retry:
                        logger.error(
                            "send error: error_count reached %d aborting",
                            error_count)
                        self.abort()
                        return False

            sent_bytes += actual_len
            sequence += 1

            if callback:
                callback(task)

        # -- EOT --
        error_count = 0
        while True:
            self.putc(EOT)
            c = self.getc()
            if not c:
                error_count += 1
                if error_count >= retry:
                    logger.error("EOT wasnt ACKd, aborting transfer")
                    self.abort()
                    return False
                continue
            if c == ACK:
                break
            elif c == NAK:
                error_count += 1
                if error_count >= retry:
                    logger.error("EOT wasnt ACKd, aborting transfer")
                    self.abort()
                    return False
            elif c == CAN:
                return False
            else:
                error_count += 1

        # -- End-of-batch (null filename packet) --
        null_data = self.header_pad * packet_size
        header = self._make_send_header(packet_size, 0)
        checksum = self._make_send_checksum(null_data)
        self.putc(header + null_data + checksum)

        # Wait for final ACK (best-effort)
        error_count = 0
        while True:
            c = self.getc()
            if not c:
                error_count += 1
                if error_count >= retry:
                    break
                continue
            if c == ACK:
                break
            else:
                error_count += 1
                if error_count >= retry:
                    break

        return True


# ═══════════════════════════════════════════════════════════════════════════
# Module-level utility functions
# Source: V1090_MODULE_AUDIT.txt lines 1088-1090
# ═══════════════════════════════════════════════════════════════════════════

def bytesToHexString(bs):
    """Convert bytes to hex string.

    Args:
        bs: bytes or bytearray

    Returns:
        Space-separated hex string (e.g. '01 AB FF').
    """
    if bs is None:
        return ''
    return ' '.join('%02X' % b for b in bs)


def call(v1, v2, v3):
    """Generic callable wrapper.

    Args:
        v1: callable
        v2, v3: arguments

    Returns:
        Result of v1(v2, v3).
    """
    return v1(v2, v3)
