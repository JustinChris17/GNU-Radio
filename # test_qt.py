#!/usr/bin/env python3
# test_fft.py

from PyQt5.QtWidgets import QApplication
from PyQt5 import sip
from gnuradio.qtgui import freq_sink_c
from gnuradio.fft import window
import sys

def main():
    # 1) Create the Qt app
    app = QApplication(sys.argv)

    # 2) Instantiate a small FFT sink
    fs = freq_sink_c(
        256,                  # fft size
        window.WIN_HAMMING,   # window type
        0,                    # center freq
        48000,                # sample rate
        "Test FFT",           # name
        1                     # number of inputs
    )

    # 3) Wrap its internal qwidget pointer into a real QWidget
    fs_widget = sip.wrapinstance(fs.qwidget(), QApplication.instance().desktop().__class__)
    # Alternatively, explicitly:
    # from PyQt5.QtWidgets import QWidget
    # fs_widget = sip.wrapinstance(fs.qwidget(), QWidget)

    # 4) Show it
    fs_widget.show()

    # 5) Enter the Qt event loop
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()