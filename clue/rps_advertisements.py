### MIT License

### Copyright (c) 2020 Kevin J. Walters

### Permission is hereby granted, free of charge, to any person obtaining a copy
### of this software and associated documentation files (the "Software"), to deal
### in the Software without restriction, including without limitation the rights
### to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
### copies of the Software, and to permit persons to whom the Software is
### furnished to do so, subject to the following conditions:

### The above copyright notice and this permission notice shall be included in all
### copies or substantial portions of the Software.

### THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
### IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
### FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
### AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
### LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
### OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
### SOFTWARE.

import struct

from adafruit_ble.advertising import Advertisement, LazyObjectField
from adafruit_ble.advertising.standard import ManufacturerData, ManufacturerDataField

### These message should really include version numbers for the
### the protocol and a descriptor for the encryption type

### From adafruit_ble.advertising
MANUFACTURING_DATA_ADT = 0xFF
ADAFRUIT_COMPANY_ID = 0x0822

### pylint: disable=line-too-long
### From https://github.com/adafruit/Adafruit_CircuitPython_BLE_BroadcastNet/blob/c6328d5c7edf8a99ff719c3b1798cb4111bab397/adafruit_ble_broadcastnet.py#L84-L85
ADAFRUIT_SEQ_ID = 0x0003

### According to https://github.com/adafruit/Adafruit_CircuitPython_BLE/blob/master/adafruit_ble/advertising/adafruit.py
### 0xf000 (to 0xffff) is for range for Adafruit customers
GM_JOIN_ID = 0xfe30
RPS_VERSION = 0xff30
RPS_ROUND_ID = 0xff74
RPS_ENC_DATA_ID = 0xff34
RPS_KEY_DATA_ID = 0xff54
RPS_ACK_ID = 0xff52
### These ID numbers have all been carefully selected to obtain a particular
### ordering of the fields within the ManufacturerData based on the current
### dict key ordering - this is bad practice and FRAGILE as the prefix
### matching falls apart if this changes

### Data formats for shared fields
_DATA_FMT_ROUND = "B"
_DATA_FMT_ACK = "B"
_SEQ_FMT = "B"


class RpsEncDataAdvertisement(Advertisement):
    """An RPS (broadcast) message.
       This sends the encrypted choice of the player.
       This is not connectable and does not elicit a scan response
       based on defaults in Advertisement parent class.
       """
    flags = None

    _PREFIX_FMT = "<B" "BHBH"
    _DATA_FMT_ENC_DATA = "8s"

    prefix = struct.pack(
        _PREFIX_FMT,
        struct.calcsize(_PREFIX_FMT) - 1,
        MANUFACTURING_DATA_ADT,
        ADAFRUIT_COMPANY_ID,
        struct.calcsize("<H" + _DATA_FMT_ENC_DATA),
        RPS_ENC_DATA_ID
    )
    manufacturer_data = LazyObjectField(
        ManufacturerData,
        "manufacturer_data",
        advertising_data_type=MANUFACTURING_DATA_ADT,
        company_id=ADAFRUIT_COMPANY_ID,
        key_encoding="<H"
    )

    sequence_number = ManufacturerDataField(ADAFRUIT_SEQ_ID, "<" + _SEQ_FMT)
    """Sequence number of the data. Used in acknowledgements."""

    enc_data = ManufacturerDataField(RPS_ENC_DATA_ID, "<" + _DATA_FMT_ENC_DATA)
    round_no = ManufacturerDataField(RPS_ROUND_ID, "<" + _DATA_FMT_ROUND)
    ack = ManufacturerDataField(RPS_ACK_ID, "<" + _DATA_FMT_ACK)
    """Round number starting at 1."""

    def __init__(self, *, enc_data=None, round_no=None, ack=None, sequence_number=None):
        """ack must be set to () to send this optional, data-less field."""
        super().__init__()
        if enc_data is not None:
            self.enc_data = enc_data
        if round_no is not None:
            self.round_no = round_no
        if ack is not None:
            self.ack = ack
        if sequence_number is not None:
            self.sequence_number = sequence_number


class RpsKeyDataAdvertisement(Advertisement):
    """An RPS (broadcast) message.
       This sends the key to decrypt the previous encrypted choice of the player.
       This is not connectable and does not elicit a scan response
       based on defaults in Advertisement parent class.
       """
    flags = None

    _PREFIX_FMT = "<B" "BHBH"
    _DATA_FMT_KEY_DATA = "8s"

    ### prefix appears to be used to determine whether an incoming
    ### packet matches this class
    ### The second struct.calcsize needs to include the _DATA_FMT for some
    ### reason I either don't know or can't remember
    prefix = struct.pack(
        _PREFIX_FMT,
        struct.calcsize(_PREFIX_FMT) - 1,
        MANUFACTURING_DATA_ADT,
        ADAFRUIT_COMPANY_ID,
        struct.calcsize("<H" + _DATA_FMT_KEY_DATA),
        RPS_KEY_DATA_ID
    )
    manufacturer_data = LazyObjectField(
        ManufacturerData,
        "manufacturer_data",
        advertising_data_type=MANUFACTURING_DATA_ADT,
        company_id=ADAFRUIT_COMPANY_ID,
        key_encoding="<H"
    )

    sequence_number = ManufacturerDataField(ADAFRUIT_SEQ_ID, "<" + _SEQ_FMT)
    """Sequence number of the data. Used in acknowledgements."""

    key_data = ManufacturerDataField(RPS_KEY_DATA_ID, "<" + _DATA_FMT_KEY_DATA)
    round_no = ManufacturerDataField(RPS_ROUND_ID, "<" + _DATA_FMT_ROUND)
    ack = ManufacturerDataField(RPS_ACK_ID, "<" + _DATA_FMT_ACK)
    """Round number starting at 1."""

    def __init__(self, *, key_data=None, round_no=None, ack=None, sequence_number=None):
        """ack must be set to () to send this optional, data-less field."""
        super().__init__()
        if key_data is not None:
            self.key_data = key_data
        if round_no is not None:
            self.round_no = round_no
        if ack is not None:
            self.ack = ack
        if sequence_number is not None:
            self.sequence_number = sequence_number


class RpsRoundEndAdvertisement(Advertisement):
    """An RPS (broadcast) message.
       This informs other players the round_no is complete.
       An important side-effect is acknowledgement of previous message.
       This is not connectable and does not elicit a scan response
       based on defaults in Advertisement parent class.
       """
    flags = None

    _PREFIX_FMT = "<B" "BHBH"

    prefix = struct.pack(
        _PREFIX_FMT,
        struct.calcsize(_PREFIX_FMT) - 1,
        MANUFACTURING_DATA_ADT,
        ADAFRUIT_COMPANY_ID,
        struct.calcsize("<H" + _DATA_FMT_ROUND),
        RPS_ROUND_ID
    )
    manufacturer_data = LazyObjectField(
        ManufacturerData,
        "manufacturer_data",
        advertising_data_type=MANUFACTURING_DATA_ADT,
        company_id=ADAFRUIT_COMPANY_ID,
        key_encoding="<H"
    )

    sequence_number = ManufacturerDataField(ADAFRUIT_SEQ_ID, "<" + _SEQ_FMT)
    """Sequence number of the data. Used in acknowledgements."""

    round_no = ManufacturerDataField(RPS_ROUND_ID, "<" + _DATA_FMT_ROUND)
    ack = ManufacturerDataField(RPS_ACK_ID, "<" + _DATA_FMT_ACK)
    """Round number starting at 1."""

    def __init__(self, *, round_no=None, ack=None, sequence_number=None):
        """ack must be set to () to send this optional, data-less field."""
        super().__init__()
        if round_no is not None:
            self.round_no = round_no
        if ack is not None:
            self.ack = ack
        if sequence_number is not None:
            self.sequence_number = sequence_number


class JoinGameAdvertisement(Advertisement):
    """A join game (broadcast) message used as the first message to work out who is playing.
       This is not connectable and does not elicit a scan response
       based on defaults in Advertisement parent class.
       """
    flags = None

    _PREFIX_FMT = "<B" "BHBH"
    _DATA_FMT = "8s"  ### this NUL pads for 8s if necessary

    prefix = struct.pack(
        _PREFIX_FMT,
        struct.calcsize(_PREFIX_FMT) - 1,
        MANUFACTURING_DATA_ADT,
        ADAFRUIT_COMPANY_ID,
        ##struct.calcsize("<H" + _SEQ_FMT + _DATA_FMT),
        struct.calcsize("<H" + _DATA_FMT),
        ##struct.calcsize("<H"),
        GM_JOIN_ID
    )
    manufacturer_data = LazyObjectField(
        ManufacturerData,
        "manufacturer_data",
        advertising_data_type=MANUFACTURING_DATA_ADT,
        company_id=ADAFRUIT_COMPANY_ID,
        key_encoding="<H"
    )

    game = ManufacturerDataField(GM_JOIN_ID, "<" + _DATA_FMT)
    """RPS choice."""

    def __init__(self, *, game=None):
        super().__init__()
        if game is not None:
            self.game = game
