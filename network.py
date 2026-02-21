# ==============================================================================
# METU Course Registration Bot
# Author: kurtulus
# Description: Advanced course registration bot with WAF bypass & RTT sync.
# ==============================================================================

from curl_cffi import requests
import time
import os
import logging
import random
import config
import re
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from twocaptcha.solver import TwoCaptcha
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

class Registration:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.user_agent = self.randomUserAgent()
        self.session = requests.Session(impersonate=self.impersonate, default_headers=False)
        self.hidden_inputs = {}
        self.sitekey = config.DEFAULT_SITEKEY
        self.logged_in = False
        self.captcha_type = 'recaptcha'
        self.isRecaptcha = True
        self.captcha_token = None

    def checkSystem(self): # Şu anlık böyle olsun. Sistem açıldığında kontrol edeceğim.
        try:
            self.request_time = datetime.now(timezone.utc)
            self.start_local = time.monotonic() ###for RTT
            response = self.session.get(self.base_url, headers=self.setHeaders(isMainPage=True), timeout=10)
            self.end_local = time.monotonic() ###for RTT
            self.response_headers = response.headers
            if response.status_code == 200: return True
            else: return False
        except requests.exceptions.RequestException:
            return False

    def getPage(self, path : str = ''):
        headers = self.setHeaders(isMainPage=(path == ''))
        url = self.base_url + path
        try:
            self.request_time = datetime.now(timezone.utc)
            self.start_local = time.monotonic() ###for RTT
            self.response = self.session.get(url, headers=headers, timeout=5)
            self.end_local = time.monotonic() ###for RTT
            self.response_headers = self.response.headers
            self.parseHiddenInputs(self.response.text)
            return self.response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"{e}. Couldn't reach the website. Please check your internet settings. Disable any vpn or proxy service if you're using.")
            return False
        
    def getAssets(self, content: str):
        soup = BeautifulSoup(content, 'html.parser')
        assets = [
            tag.get(attr)
            for tag, attr in (
                *[(link, "href") for link in soup.find_all("link", rel="stylesheet")],
                *[(script, "src") for script in soup.find_all("script", src=True)]
            )
            if tag.get(attr)
        ]
        for asset in assets:
            asset_url = urljoin(self.base_url, asset)
            try:
                time.sleep(self.jitter(0.1, 0.4))
                self.session.get(asset_url,headers=self.setHeaders(),timeout=3)
            except Exception as e:
                logger.error('Error when loading the page.')

    def prepare(self, path: str = '', get_assets: bool= True):
        logger.info('Loading the page and its assets...')
        response = self.getPage(path = path)
        if not response:
            return False
        if get_assets: 
            self.getAssets(response)
        return True

    def loginToSystem(self, user_code : str, password : str, prog_type : int = config.PROG_TYPE):
        payload = {
            'textUserCode' : user_code,
            'textPassword' : password, ###I don't know why they store passwords as plaintext. 
            'selectProgType': prog_type,
            'submitLogin' : '[ Login ]',
            **self.hidden_inputs
        }
        self.logged_in = False #Sistem her refresh de yeniden login istiyor. 
        try:
            url = self.base_url + '/main.php'
            self.response = self.session.post(url, headers=self.setHeaders(isMainPage=False), data=payload)
            self.parseHiddenInputs(self.response.text)
            self.parseCaptchaSiteKey(self.response.text)
            soup = BeautifulSoup(self.response.text, 'html.parser')
            div_logout = soup.find('div', class_='logout')
            if div_logout:
                self.logged_in = True
                logger.info('Logged in.')
            return self.logged_in
        except requests.exceptions.RequestException as e:
            logger.error(f'{e}. Error while logging in. Please check your information.')
            return False

    def registerCourse(self,course_code: int,section: int, course_category: int=8, isPrefetch: bool= False):
        if not self.logged_in:
            logger.error('There might be an error while logging in. Please restart the script.')
            return False
        if not isPrefetch:
            self.isRecaptcha = self.captcha_type=='recaptcha'
            self.captcha_token = self.solveCaptcha()
            if not self.captcha_token:
                logger.warning('Captcha failed. Retrying in a few seconds.')
                return False
        payload = {
            'textChangeCourseSection': '',
            'selectChangeCourseCategory': '1',
            'textAddCourseCode': str(course_code),
            'textAddCourseSection': str(section),
            'selectAddCourseCategory': str(course_category), ### Please visit config.py .Currently I'll use 8. I guess it's for the NTE courses.
            'g-recaptcha-response': self.captcha_token if self.isRecaptcha else None,
            'h-captcha-response': self.captcha_token if not self.isRecaptcha else None,
            'submitAddCourse': '[ Add Course ]',
            **self.hidden_inputs
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        url = self.base_url + '/main.php'
        try:
            self.response = self.session.post(url,headers=self.setHeaders(isMainPage=False), data=payload)
            self.response.raise_for_status()
            self.status = self.checkResponse(self.response.text)
            self.parseHiddenInputs(self.response.text)
            self.parseCaptchaSiteKey(self.response.text)
        except requests.exceptions.RequestException as e:
            logger.error(f'{e}. Error while registering for the course.')
            return False
        return self.status

    def registerContinously(self,course_code: int, section: int, total_attempts: int=100, avg_jitter: int=10):
        attempt = 0
        while attempt<total_attempts:
            attempt += 1
            logger.info(f'Attempt : {attempt}/{total_attempts}')
            status = self.registerCourse(course_code, section)
            if status == 'success': return True
            if status == 'error': return False
            if not status: logger.warning('Registration attempt failed. Retrying...')
            wait = self.jitter(avg_jitter*0.5, avg_jitter*1.5)
            logger.info(f'Retrying in {wait:.2f} seconds...')
            time.sleep(wait)
        logger.error('Max attempts reached. Registration failed.')
        return False
    
    def registerWaiting(self, course_code: int, section: int, opening_time_utc: datetime, user_code: str, password: str, captcha_prefetch: float = 45.0):
        logger.info('Bu okulun ben aqq.')
        self.syncClientTime()
        time_difference = getattr(self, "time_difference", timedelta(0))
        opening_time = opening_time_utc - time_difference
        logger.info(f'Opening time: {opening_time.strftime("%Y-%m-%d %H:%M:%S")} UTC. Waiting...')
        captcha_time = opening_time - timedelta(seconds=captcha_prefetch)
        while datetime.now(timezone.utc) < captcha_time:
            remaining_time = captcha_time - datetime.now(timezone.utc)
            print(f'\rRemaining time: {remaining_time.total_seconds():.2f} s', end="")
            time.sleep(0.5)
        logger.info('\nSolving captcha to prepare for course registration.')
        self.captcha_token = self.solveCaptcha()
        if not self.captcha_token:
            logger.error('Error while solving captcha.')
            return False
        logger.info('Captcha is ready. The registration page will be loading in a few seconds.')
        while datetime.now(timezone.utc) < opening_time:
            time.sleep(0.05)
        logger.info('Logging in the system and parsing inputs...')
        self.prepare(get_assets=False)
        if not self.loginToSystem(user_code=user_code,password=password):
            logger.error('Error when logging in.')
            return False
        self.isRecaptcha = self.captcha_type=='recaptcha'
        status = self.registerCourse(course_code, section, isPrefetch=True)
        if status == 'success':
            logger.info("Registered on first attempt.")
            return True
        if status == 'error':
            logger.error("Fatal error on first attempt.")
            return False
        return self.registerContinously(course_code, section, total_attempts=10, avg_jitter=3)

    def checkResponse(self,content: str):
        """Checks if registration is successful or not."""
        soup = BeautifulSoup(content, 'html.parser')
        div = soup.find('div', id='formmessage')
        if not div: 
            logger.warning('Error during registration. Retrying...')
            return 'unknown'
        div_formsg = div.text.strip()
        if not div_formsg:
            logger.info('^^^Successfully registered to the course.^^^')
            return 'success'
        if 'capacity is full:' in div_formsg:
            logger.warning('Capacity is full. Retrying in a few seconds.')
            return 'retry'
        elif 'prerequisite' in div_formsg:
            logger.error("You don't meet the prerequisite. Stopping. Change the course.")
            return 'error'
        else: return 'unknown'

    def parseHiddenInputs(self, content: str) -> bool:
        soup = BeautifulSoup(content, 'html.parser')
        hidden_inputs = soup.find_all('input', type='hidden')
        found_inputs = {}
        for tag in hidden_inputs:
            name, value = tag.get('name'), tag.get('value')
            if name and value:
                found_inputs[name] = value
        self.hidden_inputs = found_inputs
        return bool(self.hidden_inputs)
    
    def setHeaders(self, isMainPage = True):
        parsed = urlparse(self.base_url)
        host = parsed.netloc
        default_headers = {
            "Host": host,
            "Connection": "keep-alive",
            "Cache-Control": None if isMainPage else "max-age=0",
            "sec-ch-ua": f'"Not(A:Brand";v="99", "Google Chrome";v="{self.version}", "Chromium";v="{self.version}"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "Windows",
            "Origin": None if isMainPage else self.base_url,
            "Content-Type": None if isMainPage else "application/x-www-form-urlencoded",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "dnt": "1",
            "Sec-Fetch-Site": "none" if isMainPage else "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Referer": "https://www.google.com/"if isMainPage else self.base_url+'/main.php',
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "tr-TR,tr;q=0.9,en-GB;q=0.8,en-US;q=0.7,en;q=0.6"
        }
        return {k: v for k, v in default_headers.items() if v is not None} ###Normalde request None value headerları göndermez ama her ihtimale karşı.

    def parseCaptchaSiteKey(self,content: str): 
        soup = BeautifulSoup(content, 'html.parser')
        div_captcha = soup.find('div', class_ ='g-recaptcha')
        self.captcha_type = 'recaptcha'
        if not div_captcha: 
            logger.info("Couldn't find recaptcha. Finding hcaptcha if possible...")
            div_captcha = soup.find('div', class_='h-captcha')
            self.captcha_type = 'hcaptcha'
        if div_captcha:
            self.sitekey = div_captcha.get('data-sitekey')
        if not self.sitekey : self.sitekey = config.DEFAULT_SITEKEY
        return self.sitekey, self.captcha_type

    def solveCaptcha(self):
        if not self.sitekey: return False
        solver = TwoCaptcha(config.TWOCAPTCHA_API_KEY)
        try:
            if self.captcha_type == 'recaptcha':
                result = solver.recaptcha(sitekey=self.sitekey, url=self.base_url + '/main.php')
                if result: return result['code']
            elif self.captcha_type == 'hcaptcha':
                result = solver.hcaptcha(sitekey=self.sitekey, url=self.base_url + '/main.php')
                if result: return result['code']
            return False
        except Exception as e:
            logger.info(f"2Captcha error. Please check your balance or api key.")
            return False

    @classmethod
    def detectProxy(cls): #Maybe later 
        pass

    def syncClientTime(self):
        if not hasattr(self, "response_headers"): return None
        server_date = self.response_headers.get('date')
        if not server_date: return None
        server_time = parsedate_to_datetime(server_date).astimezone(timezone.utc)
        rtt = self.end_local - self.start_local
        local_time = self.request_time + timedelta(seconds=rtt/2)
        self.time_difference = server_time - local_time
        logger.info(f'The client time is synced. Time difference is {self.time_difference.total_seconds():.2f}s.')
            
    def randomUserAgent(self):
        random_im = random.choice(config.IMPERSONATES)
        self.impersonate = random_im
        match = re.match(r"(chrome|firefox)(\d+)", random_im)
        if not match:
            raise ValueError("Please check impersonates in config.py file.")
        browser , self.version = match.groups()
        template = config.USER_AGENT_TEMPLATES[browser]
        return template.format(version=self.version)

    @staticmethod
    def jitter(min_val: float, max_val: float) -> float:
        if min_val > max_val: raise ValueError('min_val cannot be greater than max_val.')
        if min_val < 0 or max_val < 0: raise ValueError('min_val or max_val cannot be negative.')
        return min_val + (max_val-min_val) * Registration.__generateRandomFloat() ###

    @staticmethod
    def __generateRandomFloat() -> float:
        temp_rand = os.urandom(8)
        rand_float = int.from_bytes(temp_rand,byteorder='big') / (1 << 64)
        return rand_float
         