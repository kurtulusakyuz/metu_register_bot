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
from urllib.parse import urljoin
import threading
import queue

logger = logging.getLogger(__name__)

class Registration:
    def __init__(self, base_url: str):
        self.base_url = base_url
        #self.user_agent = self.randomUserAgent() Şu anlık devre dışı.
        self.impersonate = random.choice(config.IMPERSONATES)
        self.session = requests.Session(impersonate=self.impersonate)
        self.hidden_inputs = {}
        self.sitekey = config.DEFAULT_SITEKEY_RECAPTCHA
        self.logged_in = False
        self.captcha_type = 'recaptcha'
        self.isRecaptcha = True
        self.captcha_token = None
        self.token_queue = queue.Queue(maxsize=2)
        self.stop_threads = False
    
    def _makeRequest(self, method: str, path='', payload: dict = None, timeout: int = 5):
        url = self.base_url + path
        isMainPage = path == ''
        headers = self.setHeaders(isMainPage=isMainPage)
        try:
            if isMainPage:
                self.request_time = datetime.now(timezone.utc)
                self.start_local = time.monotonic() ###for RTT
            if method.upper() == 'GET':
                response = self.session.get(url, headers=headers, timeout=timeout)
            elif method.upper() == 'POST':
                response = self.session.post(url, headers=headers, data=payload, timeout=timeout)
            else: return False
            response.raise_for_status()
            if isMainPage:
                self.end_local = time.monotonic() ###for RTT
                self.response_headers = response.headers
            self.parseHiddenInputs(response.text)
            if not isMainPage:
                self.parseCaptchaSiteKey(response.text)
            return response
        except requests.exceptions.Timeout as e:
            logger.error(f'Timeout error ({path}): {e}')
        except requests.exceptions.HTTPError as e:
            logger.error(f'HTTP error ({path}): {e}')
        except requests.exceptions.RequestException as e:
            logger.error(f'Request error ({path}) {e}')
        return False

    def checkSystem(self): # Şu anlık böyle olsun. Sistem açıldığında kontrol edeceğim.
        response = self._makeRequest('GET', timeout=10)
        if not response: return False
        logger.info('System is online.')
        return True

    def _getAssets(self, content: str):
        soup = BeautifulSoup(content, 'html.parser')
        assets = [tag.get(attr) for tag, attr in (*[(link, "href") for link in soup.find_all("link", rel="stylesheet")], *[(script, "src") for script in soup.find_all("script", src=True)]) if tag.get(attr)]
        for asset in assets:
            asset_url = urljoin(self.base_url, asset)
            try:
                time.sleep(self.jitter(0.1, 0.4))
                self.session.get(asset_url,headers={ "Referer" : self.base_url + '/main.php'},timeout=3)
            except Exception as e:
                logger.error('Error when loading the page.')

    def prepare(self, path: str = '', get_assets: bool= True):
        logger.info('Loading the page and its assets...')
        response = self._makeRequest(method='GET',path = path)
        if not response:
            return False
        if get_assets: 
            self._getAssets(response.text)
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
        response = self._makeRequest('POST', path='/main.php', payload=payload)
        if response:
            soup = BeautifulSoup(response.text, 'html.parser')
            if soup.find('div', class_='logout'):
                self.logged_in = True
                logger.info('Logged in.')
        return self.logged_in

    def registerCourse(self,course_code: int,section: int, course_category: int=8):
        if not self.logged_in:
            logger.error('There might be an error while logging in. Please restart the script.')
            return 'error'
        self.isRecaptcha = self.captcha_type=='recaptcha'
        while True:
            try:
                captcha_data = self.token_queue.get(timeout=60)
            except queue.Empty:
                logger.error('^Captcha pool is empty. There might be a problem.')
                self.stop_threads = True
                return 'error'
            if captcha_data.get('token') == 'ERROR':
                logger.error('Received error from captcha worker. Aborting registration.')
                return 'error'
            token_age = time.monotonic() - captcha_data['timestamp']
            if token_age > 110:
                logger.warning(f'Captcha token expired ({token_age:.1f}s old). Getting new one...')
                continue
            self.captcha_token = captcha_data['token']
            logger.info(f'Using captcha token ({token_age:.1f}s old).')
            break
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
        response = self._makeRequest('POST', path='/main.php', payload=payload)
        if response:
            status = self.checkResponse(response.text)
            return status
        else: return 'error'

    def registerContinously(self,course_code: int, section: int, total_attempts: int=100, avg_jitter: int=10):
        if not hasattr(self,'worker') or not self.worker.is_alive():
            self.stop_threads = False
            self.worker = threading.Thread(target=self.captchaWorker, daemon=True)
            self.worker.start()
        attempt = 0
        while attempt<total_attempts:
            attempt += 1
            logger.info(f'Attempt : {attempt}/{total_attempts}')
            status = self.registerCourse(course_code, section)
            if status == 'success':
                self.stop_threads = True
                return True
            if status == 'error': 
                self.stop_threads = True
                return False
            if status in ('retry', 'unknown'): logger.warning('Registration attempt failed. Retrying...')
            wait = self.jitter(avg_jitter*0.5, avg_jitter*1.5)
            logger.info(f'Retrying in {wait:.2f} seconds...')
            time.sleep(wait)
        logger.error('Max attempts reached. Registration failed.')
        self.stop_threads = True
        return False
    
    def registerWaiting(self, course_code: int, section: int, opening_time_utc: datetime, user_code: str, password: str, captcha_prefetch: float = config.CAPTCHA_PREFETCH):
        logger.info('Bu okulun ben aqq.')
        self.prepare(get_assets=False)
        self.syncClientTime()
        time_difference = getattr(self, "time_difference", timedelta(0))
        opening_time = opening_time_utc - time_difference
        logger.info(f'Opening time: {opening_time.strftime("%Y-%m-%d %H:%M:%S")} UTC. Waiting...')
        captcha_time = opening_time - timedelta(seconds=captcha_prefetch)
        while datetime.now(timezone.utc) < captcha_time:
            remaining_time = captcha_time - datetime.now(timezone.utc)
            print(f'\rRemaining time: {remaining_time.total_seconds():.2f} s', end="")
            time.sleep(0.5)
        logger.info('\n Starting solving captcha to prepare for course registration.')
        self.stop_threads = False
        self.worker = threading.Thread(target=self.captchaWorker, daemon=True)
        self.worker.start()
        while datetime.now(timezone.utc) < opening_time:
            time.sleep(0.05)
        logger.info('Logging in the system and parsing inputs...')
        self.prepare(get_assets=False)
        if not self.loginToSystem(user_code=user_code,password=password):
            logger.error('Error when logging in.')
            self.stop_threads = True
            return False
        self.isRecaptcha = self.captcha_type=='recaptcha'
        status = self.registerCourse(course_code, section)
        if status == 'success':
            logger.info("Registered on first attempt.")
            self.stop_threads = True
            return True
        if status == 'error':
            logger.error("Fatal error on first attempt.")
            self.stop_threads = True
            return False
        return self.registerContinously(course_code, section, total_attempts=10, avg_jitter=3)

    def checkResponse(self,content: str):
        """Checks if registration is successful or not."""
        soup = BeautifulSoup(content, 'html.parser')
        div = soup.find('div', id='formmessage')
        if not div: 
            logger.warning('Error during registration. Retrying...')
            return 'unknown'
        div_formsg = div.text.strip().lower()
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
        default_headers = {
            "Cache-Control": None if isMainPage else "max-age=0",
            "Origin": None if isMainPage else self.base_url,
            "Sec-Fetch-Site": "none" if isMainPage else "same-origin",
            "Referer": "https://www.google.com/"if isMainPage else self.base_url+'/main.php',
        }
        return {k: v for k, v in default_headers.items() if v is not None} ###Normalde request None value headerları göndermez ama her ihtimale karşı.

    def parseCaptchaSiteKey(self,content: str): 
        soup = BeautifulSoup(content, 'html.parser')
        div_captcha = soup.find('div', class_ ='g-recaptcha')
        self.captcha_type = 'recaptcha'
        default_sitekey= config.DEFAULT_SITEKEY_RECAPTCHA
        if not div_captcha: 
            logger.info("Couldn't find recaptcha. Finding hcaptcha if possible...")
            div_captcha = soup.find('div', class_='h-captcha')
            self.captcha_type = 'hcaptcha'
            default_sitekey = config.DEFAULT_SITEKEY_HCAPTCHA
        if div_captcha:
            self.sitekey = div_captcha.get('data-sitekey') or default_sitekey
        return self.sitekey, self.captcha_type

    def solveCaptcha(self, total_attempts: int = 3):
        if not self.sitekey: 
            logger.error('No sitekey available.')
            return False
        solver = TwoCaptcha(config.TWOCAPTCHA_API_KEY)
        for attempt in range(1,total_attempts+1):     
            try:
                logger.info(f'Solving {self.captcha_type} ({attempt}/{total_attempts})...')
                if self.captcha_type == 'recaptcha':
                    result = solver.recaptcha(sitekey=self.sitekey, url=self.base_url + '/main.php')
                elif self.captcha_type == 'hcaptcha':
                    result = solver.hcaptcha(sitekey=self.sitekey, url=self.base_url + '/main.php')
                else:
                    return None
                if result and result.get('code'):
                    logger.info('Captcha solved successfully.')
                    return result['code']
            except Exception:
                logger.warning(f'Attempt {attempt} failed.')
            if attempt < total_attempts:
                time.sleep(1.5)
        logger.error('2Captcha error. Please check your balance or api key.')
        return None
    
    def captchaWorker(self):
        logger.info('Captcha worker started.')
        error = 0
        try:
            while not self.stop_threads:
                if not self.token_queue.full():
                    result = self.solveCaptcha()
                    if result:
                        self.token_queue.put({"token": result, "timestamp" : time.monotonic()})
                        logger.info('New captcha added to the captcha pool.')
                        error = 0
                    else:
                        error += 1
                        if error >= 2:
                            self.stop_threads = True
                            try:
                                self.token_queue.put({"token": "ERROR", "timestamp": time.monotonic()}, timeout=1)
                            except queue.Full:
                                pass
                            break
                        time.sleep(3)
                else:
                    time.sleep(1)
        except Exception as e:
            logger.error(f'Captcha worker crashed: {e}')

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
            
    def randomUserAgent(self): ###Artık lazım olmayabilir. Kalsın yine de, bir problem çıkarsa kullanırım.
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
         