from network import Registration
import sys
from datetime import datetime, timezone, timedelta
import getpass
import logging
import time
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S', handlers=[logging.FileHandler("script.log", mode='a', encoding='utf-8'),logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

def printSplash():
    splash = r"""
    _______  ______ _________                     _______  _______ _________         
    (  ___  )(  __  \\__   __/|\     /|           (       )(  ____ \\__   __/|\     /|
    | (   ) || (  \  )  ) (   | )   ( |           | () () || (    \/   ) (   | )   ( |
    | |   | || |   ) |  | |   | |   | |   _____   | || || || (__       | |   | |   | |
    | |   | || |   | |  | |   | |   | |  (_____)  | |(_)| ||  __)      | |   | |   | |
    | |   | || |   ) |  | |   | |   | |           | |   | || (         | |   | |   | |
    | (___) || (__/  )  | |   | (___) |           | )   ( || (____/\   | |   | (___) |
    (_______)(______/   )_(   (_______)           |/     \|(_______/   )_(   (_______)
                                                                                    
    ===================================================================================
      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ WELCOME ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    ===================================================================================
    """
    print(splash)

def main():
    printSplash()
    logger.info('Starting METU Registration Bot. Coded by kurtulus.')
    print('Preparing...')
    time.sleep(3)
    metu = Registration('https://register.metu.edu.tr')
    logger.info('Checking if the system is online...')
    isActive = metu.checkSystem()
    if not isActive:
        logger.warning("The system hasn't opened yet.\n")
    opening_time = input('Please enter the time that system will be opening.\nThe input must be in the format of HH:MM and in Turkish clock, e.x: 10:00. Please leave empty if you want to start immediately.').strip()
    course_code, section, user_code, password = takeInputs()
    if opening_time:
        try:
            tr_timezone = timezone(timedelta(hours=3))
            now = datetime.now(tr_timezone)
            time_parts = datetime.strptime(opening_time, "%H:%M").time()
            target_time_tr = datetime.combine(now.date(), time_parts, tzinfo=tr_timezone)
            if target_time_tr < now:
                target_time_tr += timedelta(days=1)
            target_time_utc = target_time_tr.astimezone(timezone.utc)
            logger.info(f"Waiting for the target time. Target Time: {target_time_tr.strftime('%Y-%m-%d %H:%M:%S')}")
            metu.registerWaiting(course_code, section, target_time_utc, user_code=user_code, password=password)
        except ValueError:
            logger.error('The time format is wrong. Stopping...')
            sys.exit(1)    
    else:
        logger.info('No time entered. Starting immediately...')
        metu.prepare()
        metu.loginToSystem(user_code=user_code,password=password)
        if metu.logged_in:
            jitter = 20
            try:
                jitter = int(input('Please enter the number of seconds between requests (0-120s): '))
                if jitter<0 or jitter>120:
                    print("You didn't enter a number between 0 and 120. Using the optimal number.")
            except ValueError: 
                print("You didn't enter a number. Using the optimal number. (20s)")
            metu.registerContinously(course_code, section, total_attempts=config.TOTAL_ATTEMPTS, avg_jitter=jitter)
        else:
            logger.error("Couldn't login. Stopping...")
            sys.exit(1)

def takeInputs():
    try:
        course_code = int(input('Please enter the course code: '))
        section = int(input('Please enter the section you want: '))
    except ValueError:
        logger.error('Course code and section must be integers.')
        sys.exit(1)
    #course_category buraya tekrar bak
    user_code = input('Please enter your usercode: ')
    password = getpass.getpass('Please enter the password: ')
    return course_code, section,user_code, password

if __name__ == "__main__":
    main()


