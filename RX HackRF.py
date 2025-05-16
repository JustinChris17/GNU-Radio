#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: GPL-3.0
#
# Burst‑Audio Receiver (Message‑based PDU path)

from PyQt5 import Qt
from gnuradio import qtgui, blocks, digital, gr, audio
from gnuradio.fft import window
from PyQt5 import sip
import osmosdr
import numpy as np
import zlib
import pmt
import sys, signal

# --- Embedded Python Blocks (message‑based) ---
class decompress_pdu(gr.basic_block):
    """PDU handler: decompress payload with zlib"""
    def __init__(self):
        super().__init__(
            name="DecompressPDU", in_sig=None, out_sig=None
        )
        # message ports
        self.message_port_register_in(pmt.intern('in'))
        self.message_port_register_out(pmt.intern('out'))
        self.set_msg_handler(pmt.intern('in'), self.handle_msg)

    def handle_msg(self, pdu_msg):
        meta = pmt.car(pdu_msg)
        vec = pmt.cdr(pdu_msg)
        data = bytes(pmt.u8vector_elements(vec))
        try:
            payload = zlib.decompress(data)
        except zlib.error:
            return
        out_vec = pmt.init_u8vector(len(payload), list(payload))
        out_pdu = pmt.cons(meta, out_vec)
        self.message_port_pub(pmt.intern('out'), out_pdu)

# ------------------------------------------

class BurstAudioRxPDU(gr.top_block, Qt.QWidget):
    def __init__(self):
        gr.top_block.__init__(self, "Burst‑Audio Receiver PDU")
        Qt.QWidget.__init__(self)
        qtgui.util.check_set_qss()
        self.setWindowTitle("Burst‑Audio Receiver PDU")

        # layout
        layout = Qt.QVBoxLayout(self)

        # parameters
        samp_rate   = 48000
        center_freq = 915e6
        packet_len  = 128
        pkt_tag     = "burst_audio"

        # 1) Spectrum sink
        spec = qtgui.freq_sink_c(
            1024, window.WIN_BLACKMAN_HARRIS, 0, samp_rate,
            "RX Spectrum", 1
        )
        spec.set_update_time(0.10)
        spec.enable_grid(True)
        spec.set_y_axis(-140, 10)
        w = sip.wrapinstance(spec.qwidget(), Qt.QWidget)
        layout.addWidget(w)

        # 2) HackRF One #1 source
        src = osmosdr.source(args="numchan=1 hackrf=1")
        src.set_sample_rate(samp_rate)
        src.set_center_freq(center_freq)
        src.set_gain(20)

        # 3) GFSK demod + header sync
        demod = digital.gfsk_demod(
            samples_per_symbol=2,
            sensitivity=1.0,
            gain_mu=0.175,
            mu=0.5,
            omega_relative_limit=0.005,
            freq_error=0.0
        )
        sync = digital.correlate_access_code_bb_ts(
            digital.packet_utils.default_access_code,
            0, packet_len)

        # 4) Tagged stream to PDU
        ts_to_pdu = blocks.tagged_stream_to_pdu(
            gr.sizeof_char, packet_len)
        dbg = blocks.message_debug(True)

        # 5) Decompress PDU
        decomp = decompress_pdu()

        # 6) PDU to tagged stream
        from gnuradio import pdu as pdu_mod
        pdu_to_ts = pdu_mod.pdu_to_tagged_stream(
            gr.sizeof_char, packet_len)

        # 7) Stream unpack → audio
        b2s = blocks.packed_to_unpacked_bb(1, gr.GR_LSB_FIRST)
        s2f = blocks.short_to_float(1, 1/32767.0)
        audio_out = audio.sink(samp_rate, "")

        # 8) File sink
        wav_out = blocks.wavfile_sink(
            "rx_capture.wav", 1, samp_rate,
            blocks.FORMAT_WAV, blocks.FORMAT_PCM_16
        )

        # connect stream path
        self.connect(src, spec)
        self.connect(src, demod)
        self.connect(demod, sync)
        self.connect(sync, ts_to_pdu)
        # message connections
        self.msg_connect(ts_to_pdu, 'pdus', dbg, 'print_pdu')
        self.msg_connect(ts_to_pdu, 'pdus', decomp, 'in')
        self.msg_connect(decomp, 'out', pdu_to_ts, 'pdus')
        # back to stream → audio/file
        self.connect(pdu_to_ts, b2s, s2f)
        self.connect(s2f, audio_out)
        self.connect(s2f, wav_out)

    def closeEvent(self, event):
        self.stop()
        self.wait()
        event.accept()


def main():
    if gr.enable_realtime_scheduling() != gr.RT_OK:
        gr.logger('realtime').warn('Failed to enable RT scheduling')

    app = Qt.QApplication(sys.argv)
    tb = BurstAudioRxPDU()
    tb.start()
    tb.show()

    def quit(sig, frame):
        tb.stop(); tb.wait(); app.quit()
    signal.signal(signal.SIGINT, quit)
    signal.signal(signal.SIGTERM, quit)

    app.exec_()

if __name__ == '__main__':
    main()