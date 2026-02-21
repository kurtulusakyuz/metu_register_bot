# METU Registration Bot
> **DISCLAIMER:** This software is for educational purposes only. Your account may be suspended due to the use of scripts. USE THE SOFTWARE AT YOUR OWN RISK. THE AUTHORS ASSUME NO RESPONSIBILITY FOR ANY RESULTS.

This python script utilizes JA3 fingerprint impersonation and automated CAPTCHA solving to seamlessly bypass anti-bot protections. It ensures millisecond-level request precision for targeted system opening times through exact RTT (Round Trip Time) synchronization.

## Installation

1. Install the required Python dependencies by running:
   pip install -r requirements.txt

2. Register at 2captcha.com to obtain your personal API key for the automated solver.

3. Open the provided `config.py` file and fill in the empty variables with your 2Captcha API key. For the default sitekey, please send me an email :).

## Usage

1. Start the bot via terminal by running:
   python main.py

2. Follow the on-screen prompts to enter the target course code, section, your login credentials, and the exact system opening time (in HH:MM format).

3. If the registration system is already open, leave the time prompt blank and press Enter to start the continuous registration mode immediately.