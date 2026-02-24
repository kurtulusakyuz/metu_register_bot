# METU Registration Helper
> **DISCLAIMER:** This software is for educational purposes only. Your account may be suspended due to the use of scripts. USE THE SOFTWARE AT YOUR OWN RISK. THE AUTHORS ASSUME NO RESPONSIBILITY FOR ANY RESULTS.

This project is a Python automation tool I built to experiment with time-critical web registration workflows. The idea was to see how accurately I could trigger requests right when a system opens, targeting millisecond-level precision using RTT-based timing calibration, asynchronous I/O, and concurrent task handling.

While building it, I focused a lot on the networking side — reducing request latency, controlling TLS fingerprint behavior, and running CAPTCHA solving in parallel in the background so it wouldn’t block the main execution. The overall structure is designed to keep timing predictable, use resources efficiently, and stay stable even when the system is under heavy traffic.

## Installation

1. Install the required dependencies by running:
   ~~~bash
   pip install -r requirements.txt
   ~~~

2. Configure required API key inside `config.py`. For the 'default_sitekey', please send me an email. :)

## Usage

Run the script from the terminal:
   ~~~
   python main.py
   ~~~

## Notes

- Without the 'default_sitekey', the script will still work. However, if you are using the script for the first time, it will not work at the specified time during the first request.


If you find any mistake, please let me know.