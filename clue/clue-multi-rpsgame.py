### clue-multi-rpsgame v1.14
### CircuitPython massively multiplayer rock paper scissors game over Bluetooth LE

### Tested with CLUE and Circuit Playground Bluefruit Alpha with TFT Gizmo
### using CircuitPython and 5.3.0

### copy this file to CLUE/CPB board as code.py

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


import time
import gc
import os
import struct
import random

import board
import displayio
from displayio import Group
import terminalio
import digitalio
from audiocore import WaveFile
import _bleio  ### just for _bleio.BluetoothError

import neopixel
from adafruit_display_text.label import Label
### https://github.com/adafruit/Adafruit_CircuitPython_BLE
from adafruit_ble import BLERadio

from rps_advertisements import JoinGameAdvertisement, \
                               RpsEncDataAdvertisement, \
                               RpsKeyDataAdvertisement, \
                               RpsRoundEndAdvertisement
from rps_audio import SampleJukebox
from rps_crypto import bytesPad, strUnpad, generateOTPadKey, \
                       enlargeKey, encrypt, decrypt
from rps_comms import broadcastAndReceive, addrToText
from rps_display import RPSDisplay, blankScreen

### TODO
### Maybe simple version is clue only
### simple version still needs win indicator (flash text?) and a score counter

### TODO - all specifying interval and reduce this for > 4 players

### TODO - player list screen - use yellow cyan colour coding for consistency

### Complex version demos how to

### use neopixels as alternative display (light 1, 2, 3 discreetly (discrete joke)

### simple version will have a lot of issues
### unreliable transport
### lack of synchronised win announcement
### need sequence number for packets and acks
### need higher level round numbers to detect out of synch
### need to work out who is who with N player games
### probably not deal with players who join midway?
### need to allocate player numbers - could sort by MAC - ACTUALLY this is not needed?!
### avoid election algorithms even if tempted
### got to decide whether to do the littany of crypto mistakes or not - ALREADY HAVE ONE!
### could do own crypto
### could include the lack of protocol versioning and future proofing and cite
### LDAP as good example and git perhaps as less good
### complex format not compatible with simple format so mixing the two will confuse things

### Other things of interest
### https://github.com/adafruit/Adafruit_CircuitPython_BLE_Eddystone
### A Service: https://github.com/adafruit/Adafruit_CircuitPython_BLE_iBBQ/blob/master/adafruit_ble_ibbq.py
### Yet another UART, implements TransparentUARTService(Service) https://github.com/adafruit/Adafruit_CircuitPython_BLE_BerryMed_Pulse_Oximeter
### A Service: https://github.com/adafruit/Adafruit_CircuitPython_BLE_Heart_Rate/blob/master/adafruit_ble_heart_rate.py
### EddystoneAdvertisement(Advertisement): https://github.com/adafruit/Adafruit_CircuitPython_BLE_Eddystone/blob/master/adafruit_ble_eddystone/__init__.py

### https://github.com/adafruit/Adafruit_CircuitPython_BLE_Apple_Notification_Center
### https://github.com/adafruit/Adafruit_CircuitPython_BLE_MIDI

### Dan's latest handiwork
### https://github.com/adafruit/Adafruit_CircuitPython_BLE_Adafruit

### https://learn.adafruit.com/bluetooth-le-broadcastnet-sensor-node-raspberry-pi-wifi-bridge
### explains the https://github.com/adafruit/Adafruit_CircuitPython_BLE_BroadcastNet


### These imports works on CLUE, CPB (and CPX on 5.x)
from audiocore import RawSample
try:
    from audioio import AudioOut
except ImportError:
    from audiopwmio import PWMAudioOut as AudioOut

### Look for ble_name in secrets.py file if present
ble_name = None
try:
    from secrets import secrets
    ble_name = secrets.get("rps_name")
    if ble_name is None:
        ble_name = secrets.get("ble_name")
        if ble_name is None:
            print("INFO: No rps_name or ble_name entry found in secrets dict")
except ImportError:
    pass


debug = 3

def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


def tftGizmoPresent():
    """Determine if the TFT Gizmo is attached.
       The TFT's Gizmo circuitry for backlight features a 10k pull-down resistor.
       This attempts to verify the presence of the pull-down to determine
       if TFT Gizmo is present.
       This is likely to get confused if anything else is connected to pad A3.
       Only use this on Circuit Playground Express (CPX)
       or Circuit Playground Bluefruit (CPB) boards."""
    present = True
    try:
        with digitalio.DigitalInOut(board.A3) as backlight_pin:
            backlight_pin.pull = digitalio.Pull.UP
            present = not backlight_pin.value
    except ValueError:
        ### The Gizmo is already initialised, i.e. showing console output
        pass

    return present


### Assuming CLUE if it's not a Circuit Playround (Bluefruit)
clue_less = "Circuit Playground" in os.uname().machine

### Note: difference in pull-up and pull-down
###       and logical not use for buttons
if clue_less:
    ### CPB with TFT Gizmo (240x240)
    ### from adafruit_circuitplayground import cp  ### Avoiding to save memory

    ### Outputs
    if tftGizmoPresent():
        from adafruit_gizmo import tft_gizmo
        display = tft_gizmo.TFT_Gizmo()
        JG_RX_COL = 0x0000ff
        BUTTON_Y_POS = 120
    else:
        display = None
        JG_RX_COL = 0x000030  ### dimmer blue for upward facing CPB NeoPixels

    audio_out = AudioOut(board.SPEAKER)
    ###pixels = cp.pixels
    pixels = neopixel.NeoPixel(board.NEOPIXEL, 10)

    ### Enable the onboard amplifier for speaker
    ###cp._speaker_enable.value = True  ### pylint: disable=protected-access
    speaker_enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
    speaker_enable.switch_to_output(value=False)
    speaker_enable.value = True

    ### Inputs
    ### buttons reversed if it is used upside-down with Gizmo
    _button_a = digitalio.DigitalInOut(board.BUTTON_A)
    _button_a.switch_to_input(pull=digitalio.Pull.DOWN)
    _button_b = digitalio.DigitalInOut(board.BUTTON_B)
    _button_b.switch_to_input(pull=digitalio.Pull.DOWN)
    if display is None:
        button_left = lambda: _button_a.value
        button_right = lambda: _button_b.value
        ##button_left = lambda: cp.button_a
        ##button_right = lambda: cp.button_b

    else:
        button_left = lambda: _button_b.value
        button_right = lambda: _button_a.value
        ##button_left = lambda: cp.button_b
        ##button_right = lambda: cp.button_a

else:
    ### CLUE with builtin screen (240x240)
    ### from adafruit_clue import clue  ### Avoiding to save memory

    ### Outputs
    display = board.DISPLAY
    audio_out = AudioOut(board.SPEAKER)
    ###pixels = clue.pixel
    pixels = neopixel.NeoPixel(board.NEOPIXEL, 1)
    JG_RX_COL = 0x0000ff
    BUTTON_Y_POS = 152

    ### Inputs
    _button_a = digitalio.DigitalInOut(board.BUTTON_A)
    _button_a.switch_to_input(pull=digitalio.Pull.UP)
    _button_b = digitalio.DigitalInOut(board.BUTTON_B)
    _button_b.switch_to_input(pull=digitalio.Pull.UP)
    button_left = lambda: not _button_a.value
    button_right = lambda: not _button_b.value
    ##button_left = lambda: clue.button_a
    ##button_right = lambda: clue.button_b

blankScreen(display, pixels)

IMAGE_DIR = "rps/images"
AUDIO_DIR = "rps/audio"

files = (("searching", "welcome-to", "arena", "ready")
          + ("rock", "paper", "scissors")
          + ("start-tx", "end-tx", "txing")
          + ("rock-scissors", "paper-rock", "scissors-paper")
          + ("you-win", "draw", "you-lose", "error")
          + ("humiliation", "excellent"))

gc.collect()
d_print(2, "GC before SJ", gc.mem_free())
sample = SampleJukebox(audio_out, files,
                       directory=AUDIO_DIR, error_output=True)
del files  ### not needed anymore
gc.collect()
d_print(2, "GC after SJ", gc.mem_free())

### This limit is based on displaying names on screen with scale=2 font
MAX_PLAYERS = 8

rps_display = RPSDisplay(display, pixels, 
                         sample,
                         MAX_PLAYERS, BUTTON_Y_POS,
                         IMAGE_DIR + "/rps-sprites-ind4.bmp")

### Some code is dependent on these being lower-case
CHOICES = ("rock", "paper", "scissors")

### Transmit maximum times in seconds
JG_MSG_TIME_S = 20
FIRST_MSG_TIME_S = 12
STD_MSG_TIME_S = 4
LAST_ACK_TIME_S = 1.5


### Intro screen with audio
rps_display.introductionScreen()

### Enable the Bluetooth LE radio and set player's name (from secrets.py)
ble = BLERadio()
if ble_name is not None:
    ble.name = ble_name


game_no = 1
round_no = 1
wins = 0
losses = 0
draws = 0
voids = 0

### TOTAL_ROUNDS = 5
TOTAL_ROUNDS = 3

CRYPTO_ALGO = "chacha20"
KEY_SIZE = 8  ### in bytes
KEY_ENLARGE = 256 // KEY_SIZE // 8


def evaluateRound(mine, yours):
    """Determine who won the game based on the two strings mine and yours.
       Returns three booleans (win, draw, void)."""
    ### Return with void at True if any input is None
    try:
        mine_lc = mine.lower()
        yours_lc = yours.lower()
    except AttributeError:
        return (False, False, True)

    win = draw = void = False
    if (mine_lc == "rock" and yours_lc == "rock" or
        mine_lc == "paper" and yours_lc == "paper" or
        mine_lc == "scissors" and yours_lc == "scissors"):
        draw = True
    elif (mine_lc == "rock" and yours_lc == "paper"):
        lose = True
    elif (mine_lc == "rock" and yours_lc == "scissors"):
        win = True
    elif (mine_lc == "paper" and yours_lc == "rock"):
        win = True
    elif (mine_lc == "paper" and yours_lc == "scissors"):
        lose = True
    elif (mine_lc == "scissors" and yours_lc == "rock"):
        lose = True
    elif (mine_lc == "scissors" and yours_lc == "paper"):
        win = True
    else:
        void = True

    return (win, draw, void)


### A lookup table in Dict form for win/lose
### does not need to cater for draw condition
WAV_VICTORY_NAME = { "rp": "paper-rock",
                     "pr": "paper-rock",
                     "ps": "scissors-paper",
                     "sp": "scissors-paper",
                     "sr": "rock-scissors",
                     "rs": "rock-scissors"}

def winnerWav(mine_idx, yours_idx):
    """Return the sound file to play to describe victory or None for draw."""

    ### Take the first characters
    mine = CHOICES[mine_idx][0]
    yours = CHOICES[yours_idx][0]

    return WAV_VICTORY_NAME.get(mine + yours)

playerlist_group = playerListScreen(display)

def addPlayer(name, addr_text, address, ad):
    global players

    players.append((name, addr_text))
    rps_display.addPlayer(name)


### Make a list of all the player's (name, mac address as text)
### where both are strings with this player as first entry
players = []
my_name = ble.name
rps_display.fadeUpDown("down")
addPlayer(my_name, addrToText(ble.address_bytes), None, None)

### Join Game
gc.collect()
d_print(2, "GC before JG", gc.mem_free())

sample.play("searching", loop=True)
rps_display.fadeUpDown("up")
jg_msg = JoinGameAdvertisement(game="RPS")
(_, _, _) = broadcastAndReceive(ble,
                                jg_msg,
                                scan_time=JG_MSG_TIME_S,
                                scan_response_request=True,
                                ad_cb=lambda _a, _b, _c: rps_display.flashNeoPixels(JG_RX_COL) if JG_FLASH else None,
                                endscan_cb=lambda _a, _b, _c: button_left(),
                                name_cb=addPlayer)
_ = None  ### Clear to allow GC
sample.stop()
### Wait for button release - this stops a long press
### being acted upon in the main loop further down
while button_left():
    pass

scores = [0] * len(players)
num_other_players = len(players) - 1

gc.collect()
d_print(2, "GC after JG", gc.mem_free())

d_print(1, "PLAYERS", players)

### Sequence numbers - real packets start at 1
seq_tx = [1]  ### The next number to send
seq_rx_by_addr = {pma: 0 for pn, pma in players[1:]}  ### Per address received all up to

new_round_init = True

### A nonce by definition must not be reused but here a random key is
### generated per round and this is used once per round so this is ok
static_nonce = bytes(range(12, 0, -1))

while True:
    ### TODO - physically test this for need for debounce on left button

    if round_no > TOTAL_ROUNDS:
        print("Summary: ",
              "wins {:d}, losses {:d}, draws {:d}, void {:d}\n\n".format(wins, losses, draws, voids))

        rps_display.showGameResult(players, scores, rounds_tot=TOTAL_ROUNDS)

        ### Reset variables for another game
        round_no = 1
        wins = 0
        losses = 0
        draws = 0
        voids = 0
        scores = [0] * len(players)
        game_no += 1

    if new_round_init:
        rps_display.showGameRound(game_no=game_no, round_no=round_no, rounds_tot=TOTAL_ROUNDS)
        ### Make a new initial random choice for the player and show it
        my_choice_idx = random.randrange(len(CHOICES))
        rps_display.fadeUpDown("down")
        rps_display.showChoice(my_choice_idx,
                               game_no=game_no, round_no=round_no, rounds_tot=TOTAL_ROUNDS,
                               won_sf=wins, drew_sf=draws, lost_sf=losses)
        rps_display.fadeUpDown("up")
        new_round_init = False

    if button_left():
        while button_left():  ### Wait for button release
            pass
        my_choice_idx = (my_choice_idx + 1) % len(CHOICES)
        rps_display.showChoice(my_choice_idx,
                               game_no=game_no, round_no=round_no, rounds_tot=TOTAL_ROUNDS,
                               won_sf=wins, drew_sf=draws, lost_sf=losses)

    if button_right():
        gc.collect()
        d_print(2, "GC before comms", gc.mem_free())

        ### This sound cue is really for other players
        sample.play("ready")

        my_choice = CHOICES[my_choice_idx]
        player_choices = [my_choice]

        ### Repeating key four times to make key for ChaCha20
        short_key = generateOTPadKey(KEY_SIZE)
        key = enlargeKey(short_key, KEY_ENLARGE)
        d_print(3, "KEY", key)

        plain_bytes = bytesPad(my_choice, size=8, pad=0)
        cipher_bytes = encrypt(plain_bytes, key, CRYPTO_ALGO,
                               nonce=static_nonce)
        enc_data_msg = RpsEncDataAdvertisement(enc_data=cipher_bytes,
                                               round_no=round_no)

        ### Wait for ready sound sample to stop playing
        sample.wait()
        sample.play("start-tx")
        sample.wait()
        sample.play("txing", loop=True)
        ### Players will not be synchronised at this point as they do not
        ### have to make their choices simultaneously - much longer 12 second
        ### time to accomodate this
        _, enc_data_by_addr, _ = broadcastAndReceive(ble,
                                                     enc_data_msg,
                                                     RpsEncDataAdvertisement,
                                                     RpsKeyDataAdvertisement,
                                                     scan_time=FIRST_MSG_TIME_S,
                                                     receive_n=num_other_players,
                                                     seq_tx=seq_tx,
                                                     seq_rx_by_addr=seq_rx_by_addr)

        key_data_msg = RpsKeyDataAdvertisement(key_data=short_key, round_no=round_no)
        ### All of the programs will be loosely synchronised now
        _, key_data_by_addr, _ = broadcastAndReceive(ble,
                                                     key_data_msg,
                                                     RpsEncDataAdvertisement,
                                                     RpsKeyDataAdvertisement,
                                                     RpsRoundEndAdvertisement,
                                                     scan_time=STD_MSG_TIME_S,
                                                     receive_n=num_other_players,
                                                     seq_tx=seq_tx,
                                                     seq_rx_by_addr=seq_rx_by_addr,
                                                     ads_by_addr=enc_data_by_addr)
        del enc_data_by_addr

        ### Play end transmit sound while doing next decrypt bit
        sample.play("end-tx")

        ### TODO tidy up comments here on the purpose of RoundEnd
        ### ???? With ackall RoundEnd has no purpose and wasn't really working as a substitute anyway
        re_msg = RpsRoundEndAdvertisement(round_no=round_no)
        ### The round end message is really about acknowledging receipt of the key
        ### by sending a message that holds non-critical information
        ### TODO - this one should only send for a few second, JoinGame should send for loads
        _, re_by_addr, _ = broadcastAndReceive(ble,
                                               re_msg,
                                               RpsEncDataAdvertisement,
                                               RpsKeyDataAdvertisement,
                                               RpsRoundEndAdvertisement,
                                               scan_time=LAST_ACK_TIME_S,
                                               receive_n=num_other_players,
                                               seq_tx=seq_tx,
                                               seq_rx_by_addr=seq_rx_by_addr,
                                               ads_by_addr=key_data_by_addr)
        del key_data_by_addr
        _ = None  ### Allow old value of _ to be GC'd, del does not work on _
        ### This will have accumulated all the messages for this round
        allmsg_by_addr = re_by_addr
        del re_by_addr

        ### Decrypt results
        ### If any data is incorrect the opponent_choice is left as None
        for p_idx1 in range(1, len(players)):
            print("DECRYPT GC", p_idx1, gc.mem_free())
            opponent_name = players[p_idx1][0]
            opponent_macaddr = players[p_idx1][1]
            opponent_choice = None
            opponent_msgs = allmsg_by_addr.get(opponent_macaddr)
            if opponent_msgs is None:
                opponent_msgs = []
            cipher_ad = None
            cipher_bytes = None
            cipher_round = None
            key_ad = None
            key_bytes = None
            key_round = None
            ### There should be either one or two messges per type
            ### two occurs when there
            for msg_idx in range(len(opponent_msgs)):
                if (cipher_ad is None
                    and isinstance(opponent_msgs[msg_idx][0], RpsEncDataAdvertisement)):
                    cipher_ad = opponent_msgs[msg_idx][0]
                    cipher_bytes = cipher_ad.enc_data
                    cipher_round = cipher_ad.round_no
                elif (key_ad is None
                      and isinstance(opponent_msgs[msg_idx][0], RpsKeyDataAdvertisement)):
                    key_ad = opponent_msgs[msg_idx][0]
                    key_bytes = key_ad.key_data
                    key_round = key_ad.round_no

            if cipher_ad and key_ad:
                if round_no == cipher_round == key_round:
                    key = enlargeKey(key_bytes, KEY_ENLARGE)
                    plain_bytes = decrypt(cipher_bytes, key, CRYPTO_ALGO,
                                          nonce=static_nonce)
                    opponent_choice = strUnpad(plain_bytes)
                else:
                    print("Received wrong round for {:d} {:d}: {:d} {:d}",
                          opponent_name, round_no, cipher_round, key_round)
            else:
                print("Missing packets: RpsEncDataAdvertisement "
                      "and RpsKeyDataAdvertisement:", cipher_ad, key_ad)
            player_choices.append(opponent_choice)

        ### Free up some memory by deleting any data that's no longer needed
        del allmsg_by_addr
        gc.collect()  ### TODO - try removing this
        d_print(2, "GC after comms", gc.mem_free())

        ### Ensure end-tx has completed
        sample.wait()

        ### Chalk up wins and losses - checks this player but also has to
        ### check other players against each other to calculate all the
        ### scores for the high score table at the end of game
        for p_idx0, (p0_name, _) in enumerate(players[:len(players) - 1]):
            for p_idx1, (p1_name, _) in enumerate(players[p_idx0 + 1:], p_idx0 + 1):
                ### evaluateRound takes text strings for RPS
                (win, draw, void) = evaluateRound(player_choices[p_idx0],
                                                  player_choices[p_idx1])

                ### this_player is used to control incrementing the summary
                ### for the tally for this local player
                this_player = 0
                if p_idx0 == 0:
                    this_player = 1
                    p0_ch_idx = None
                    p1_ch_idx = None
                    try:
                        p0_ch_idx = CHOICES.index(player_choices[p_idx0])
                        p1_ch_idx = CHOICES.index(player_choices[p_idx1])
                    except ValueError:
                        void = True  ### Ensure this is marked void
                        print("ERROR", "failed to decode",
                              player_choices[p_idx0], player_choices[p_idx1])

                    ### showPlayerVPlayer takes int index values for RPS
                    rps_display.showPlayerVPlayer(p0_name, p1_name, p_idx1,
                                                  p0_ch_idx, p1_ch_idx,
                                                  win, draw, void)

                if void:
                    voids += this_player
                elif draw:
                    draws += this_player
                    scores[p_idx0] += 1
                    scores[p_idx1] += 1
                elif win:
                    wins += this_player
                    scores[p_idx0] += 2
                else:
                    losses += this_player
                    scores[p_idx1] += 2

                d_print(2,
                        p0_name, player_choices[p_idx0], "vs",
                        p1_name, player_choices[p_idx1],
                        "win", win, "draw", draw, "void", void)

        print("Game {:d}, round {:d}, wins {:d}, losses {:d}, draws {:d}, "
              "void {:d}".format(game_no, round_no, wins, losses, draws, voids))

        round_no += 1
        new_round_init = True
