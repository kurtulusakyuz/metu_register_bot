USER_AGENT_TEMPLATES = {
    "chrome": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/{version}.0.0.0 Safari/537.36"
    ),
    "firefox": (
        "Mozilla/5.0 (Windows NT 10.0; rv:{version}.0) "
        "Gecko/20100101 Firefox/{version}.0"
    ),
}

IMPERSONATES = ['chrome142','firefox144']

CAPTCHA_PREFETCH = 45
CAPTCHA_TIMEOUT = 99
TOTAL_ATTEMPTS = 2000
TWOCAPTCHA_API_KEY = ''
DEFAULT_SITEKEY = '' #Send me an email.
PROG_TYPE = 1
# FILL WITH THE INTEGER THAT SUITS YOU
# 1 Major
# 2 Double Major
# 3 Minor
# 4 Teaching Certificate