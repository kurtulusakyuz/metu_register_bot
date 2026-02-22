# METU Registration Helper
> **DISCLAIMER:** This software is for educational purposes only. Your account may be suspended due to the use of scripts. USE THE SOFTWARE AT YOUR OWN RISK. THE AUTHORS ASSUME NO RESPONSIBILITY FOR ANY RESULTS.

This python script utilizes JA3 fingerprint impersonation and automated CAPTCHA solving to seamlessly bypass anti-bot protections. It ensures millisecond-level request precision for targeted system opening times through exact RTT (Round Trip Time) synchronization.

## Installation

1. Install the required dependencies by running:
   ~~~bash
   pip install -r requirements.txt
   ~~~

2. Register at 2captcha.com to obtain your personal API key for the automated solver.

3. Open the provided `config.py` file and fill in the empty variables with your 2Captcha API key. For the default_sitekey, please send me an email. :)

## Usage

Start the bot via terminal by running:
   ~~~
   python main.py
   ~~~

## Notes

- Without the default_sitekey, the script will still work. However, if you are using the script for the first time, it will not work at the specified time during the first request.


If you find any mistake, please let me know.