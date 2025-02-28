####################################################################################################
# FINAL_SETTLEMENT_SYSTEM.PY (최종 수정본 v7.3.9)
# 작성일: 2025-02-27
#
# [변경 사항]
# 1. 모든 텍스트 입력창은 5초 단위로 업데이트되며, 값이 없으면 "0"으로 표시됨.
# 2. 자동 데이터는 빨간색, 수동 입력 시 흰색으로 표시됨.
# 3. GUI는 2열 레이아웃으로 구성되어 왼쪽 열에는 B.C, 합계, 정산 결과
#    (B.C는 config에 otp_xpath가 있을 경우에만 OTP 입력창/전송 버튼이 보임),
#    오른쪽 열에는 VECT PAY, WING PAY, LEVEL 장, 개인장 출금, 개인장 잔액이 spacing 3으로 균일하게 배치됨.
# 4. 수정/전송 버튼은 AnimatedButton 클래스로, 버튼 크기는 60×30, 테두리는 제거되며,
#    수정 버튼 클릭 시 입력창의 텍스트 전체가 자동 선택되고, 완료 상태에서는 입력창이 읽기전용으로 전환되며
#    애니메이션 효과와 함께 배경색이 변경되어 잠금 상태임을 표시함.
# 5. OTP 입력창은 6자리 입력에 맞게 크기를 100×30으로, 전송 버튼은 60×30으로 설정되며,
#    animate_otp()를 통해 2초 동안 서서히 나타남.
# 6. WING PAY는 로그인 후 NASDAQ URL에서 5초마다 새로고침하며 xpath 정보를 취득함.
# 7. VECT PAY는 네이버 로그인 URL로 접속 후 "아이디에요"/"비번이에요"를 입력, 로그인 버튼 클릭 후
#    15초 대기 후 "https://www.winglobalpay.com/" URL로 이동하여, 로딩 후 2초, 2초, 3초, 3초, 3초씩 기다리며
#    차례로 아래 xpath 요소들을 클릭/입력하여 최종 정보를 크롤링함.
#       - /html/body/div[1]/div[1]/header/button[1]
#       - /html/body/div[1]/div[2]/nav/ul/li[2]/a
#       - /html/body/div[1]/div[2]/nav/ul/li[2]/ul/li[1]/a
#       - /html/body/div[1]/div[6]/ul/li[5]/a
#       - /html/body/div[1]/div[4]/div[3]/form/div/div[1]/input 에 "안녕 잘입력되고 있어 굿바이" 입력
#       - /html/body/div[1]/div[4]/div[3]/div[4]/button[1] 클릭
# 8. OTP 위젯은 기본적으로 숨김 처리되며, 해당 요소가 확인되면 animate_otp()를 통해 서서히 나타남.
# 9. 정산 결과가 비정상일 경우, "증복입금 혹은 오승인 확인 요망." 또는 "입금 후 미신청 또는 핑돈 확인 요망." 문구가 표시되는데,
#    후자의 경우 글자 크기를 15pt, 굵게 표시하고, 정산 시각도 동일한 크기와 굵은 글씨(파란색 유지)로 표시됨.
#    정상인 경우 모든 텍스트가 초록색으로 표시됨.
# 10. 메인 GUI 창은 400x300 크기로 최소화되어 있으며, 각 열 및 위젯 간 여백은 spacing 3으로 균일하게 배치됨.
####################################################################################################

import sys, os, time, re, atexit, subprocess, functools
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel,
    QMainWindow, QMessageBox, QHBoxLayout, QStackedWidget, QGroupBox, QGridLayout,
    QGraphicsOpacityEffect, QFormLayout, QInputDialog
)
from PyQt5.QtCore import QRegExp, Qt, QTimer, QPropertyAnimation, pyqtSignal, QThread, QUrl, QVariantAnimation
from PyQt5.QtGui import QGuiApplication, QDesktopServices, QRegExpValidator, QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

##############################################
# AnimatedButton: 수정/전송 버튼 (호버 효과 및 스타일)
##############################################
class AnimatedButton(QPushButton):
    def __init__(self, text=""):
        super().__init__(text)
        self.setStyleSheet("background-color: #2196F3; border: none; border-radius: 10px; font-size: 13pt; color: white;")
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(500)
        self.anim.valueChanged.connect(self.on_value_changed)
    def on_value_changed(self, value):
        base_color = QColor("#2196F3")
        hover_color = QColor("#0D47A1")
        r = base_color.red() + (hover_color.red() - base_color.red()) * value
        g = base_color.green() + (hover_color.green() - base_color.green()) * value
        b = base_color.blue() + (hover_color.blue() - base_color.blue()) * value
        new_color = QColor(int(r), int(g), int(b))
        self.setStyleSheet(f"background-color: {new_color.name()}; border: none; border-radius: 10px; font-size: 13pt; color: white;")
    def enterEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()
        super().enterEvent(event)
    def leaveEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.start()
        super().leaveEvent(event)

##############################################
# NumberLineEdit (자동 업데이트/수동 입력창)
##############################################
class NumberLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 폭을 200으로 늘려 100억까지 입력 가능하게 함.
        self.setFixedWidth(200)
        self.setValidator(QRegExpValidator(QRegExp("^[0-9]{0,11}$"), self))
        self.textChanged.connect(self.formatText)
    def formatText(self, text):
        self.blockSignals(True)
        digits = text.replace(",", "")
        if digits == "":
            self.blockSignals(False)
            return
        try:
            num = int(digits)
            formatted = f"{num:,}"
            self.setText(formatted)
        except Exception:
            pass
        self.blockSignals(False)

##############################################
# create_chrome_driver, non_headless_options
##############################################
def create_chrome_driver(options, retries=3):
    for i in range(retries):
        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            return driver
        except Exception as e:
            print(f"Chrome 드라이버 초기화 오류 (시도 {i+1}/{retries}): {e}")
            time.sleep(2)
    return None

non_headless_options = webdriver.ChromeOptions()

##############################################
# 헬퍼 함수들
##############################################
class CopyableLineEdit(QLineEdit):
    def mousePressEvent(self, event):
        QGuiApplication.clipboard().setText(self.text())
        super().mousePressEvent(event)

class CopyableLabel(QLabel):
    def mousePressEvent(self, event):
        QGuiApplication.clipboard().setText(self.text())
        super().mousePressEvent(event)

def format_number(value):
    if not value.strip():
        return "0"
    try:
        num = float(value.replace(",", "").strip())
        return f"{int(num):,}"
    except Exception:
        return value

##############################################
# 사이트별 크롤링 스레드
##############################################
class SiteAutomationThread(QThread):
    automation_complete = pyqtSignal(str)
    otp_ready = pyqtSignal(str)
    otp_hide = pyqtSignal(str)
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
    def run(self):
        if self.config['site_name'] == "VECT PAY":
            try:
                driver = create_chrome_driver(non_headless_options)
                if not driver:
                    self.automation_complete.emit("Driver Init Failed")
                    return
                driver.maximize_window()
                driver.get(self.config['login_url'])
                WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config['login_id_xpath'])))
                time.sleep(15)
                driver.find_element(By.XPATH, self.config['login_id_xpath']).clear()
                driver.find_element(By.XPATH, self.config['login_id_xpath']).send_keys(self.config['login_id'])
                driver.find_element(By.XPATH, self.config['login_pw_xpath']).clear()
                driver.find_element(By.XPATH, self.config['login_pw_xpath']).send_keys(self.config['login_pw'])
                driver.find_element(By.XPATH, self.config['login_button_xpath']).click()
                time.sleep(15)
                if self.config.get('otp_xpath', "").strip():
                    try:
                        otp_field = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config['otp_xpath'])))
                        self.otp_ready.emit(self.config['site_name'])
                        while self.config.get('otp_value', '') == '':
                            time.sleep(0.5)
                        otp_to_send = self.config.get('otp_value', '')
                        if otp_to_send:
                            otp_field.clear()
                            otp_field.send_keys(otp_to_send + Keys.ENTER)
                            self.config['otp_value'] = ''
                            time.sleep(15)
                    except Exception as e:
                        print("B.C OTP 요소 미발견:", e)
                time.sleep(3)
                # VECT PAY의 경우, final_crawl_xpath에서 추출되는 원본 문자열에서
                # 두 번째 등장하는 숫자부터 '-' 전까지의 숫자만 추출하고 천단위 콤마 포맷 적용
                while True:
                    time.sleep(3)
                    driver.refresh()
                    elem = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config['final_crawl_xpath'])))
                    raw_text = elem.text
                    matches = list(re.finditer(r'\d+', raw_text))
                    if len(matches) >= 2:
                        second_match = matches[1]
                        remaining_text = raw_text[second_match.start():]
                        dash_index = remaining_text.find(':')
                        if dash_index != -1:
                            number_str = remaining_text[:dash_index]
                        else:
                            number_str = remaining_text
                        number_list = re.findall(r'\d+', number_str)
                        if number_list:
                            number_str = number_list[0]
                        else:
                            number_str = "0"
                        formatted_number = f"{int(number_str):,}"
                        text = formatted_number
                    else:
                        text = "0"
                    self.automation_complete.emit(text)
            except Exception as e:
                print("VECT PAY 크롤링 오류:", e)
                self.automation_complete.emit("Automation Error")
            finally:
                time.sleep(15)
                driver.quit()
            return

        elif self.config['site_name'] == "B.C":
            try:
                driver = create_chrome_driver(non_headless_options)
                if not driver:
                    self.automation_complete.emit("Driver Init Failed")
                    return
                driver.maximize_window()
                driver.get(self.config['login_url'])
                WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config['login_id_xpath'])))
                time.sleep(15)
                driver.find_element(By.XPATH, self.config['login_id_xpath']).clear()
                driver.find_element(By.XPATH, self.config['login_id_xpath']).send_keys(self.config['login_id'])
                driver.find_element(By.XPATH, self.config['login_pw_xpath']).clear()
                driver.find_element(By.XPATH, self.config['login_pw_xpath']).send_keys(self.config['login_pw'])
                driver.find_element(By.XPATH, self.config['login_button_xpath']).click()
                time.sleep(5)
                if self.config.get('otp_xpath', "").strip():
                    try:
                        otp_field = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config['otp_xpath'])))
                        self.otp_ready.emit(self.config['site_name'])
                        while self.config.get('otp_value', '') == '':
                            time.sleep(0.5)
                        otp_to_send = self.config.get('otp_value', '')
                        if otp_to_send:
                            otp_field.clear()
                            otp_field.send_keys(otp_to_send + Keys.ENTER)
                            self.config['otp_value'] = ''
                            time.sleep(5)
                    except Exception as e:
                        print("B.C OTP 요소 미발견:", e)
                time.sleep(15)
                # B.C는 로그인 후 post_login_url에서 최종 정보를 취득하도록 함.
                driver.get(self.config['post_login_url'])
                while True:
                    time.sleep(5)
                    driver.refresh()
                    elem = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config['final_crawl_xpath'])))
                    text = elem.text
                    if '.' in text:
                        text = text.split('.')[0]
                    self.automation_complete.emit(text)
            except Exception as e:
                print("B.C 크롤링 오류:", e)
                self.automation_complete.emit("Automation Error")
            finally:
                self.otp_hide.emit(self.config['site_name'])
                time.sleep(5)
                driver.quit()
            return

        elif self.config['site_name'] == "WING PAY":
            try:
                driver = create_chrome_driver(non_headless_options)
                if not driver:
                    self.automation_complete.emit("Driver Init Failed")
                    return
                driver.maximize_window()
                driver.get(self.config['login_url'])
                WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config['login_id_xpath'])))
                time.sleep(20)
                driver.find_element(By.XPATH, self.config['login_id_xpath']).clear()
                driver.find_element(By.XPATH, self.config['login_id_xpath']).send_keys(self.config['login_id'])
                driver.find_element(By.XPATH, self.config['login_pw_xpath']).clear()
                driver.find_element(By.XPATH, self.config['login_pw_xpath']).send_keys(self.config['login_pw'])
                driver.find_element(By.XPATH, self.config['login_button_xpath']).click()
                time.sleep(15)
                driver.get("https://m.stock.naver.com/worldstock/home/USA/marketValue/NASDAQ")
                while True:
                    time.sleep(15)
                    driver.refresh()
                    elem = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config['final_crawl_xpath'])))
                    text = elem.text
                    if '.' in text:
                        text = text.split('.')[0]
                    self.automation_complete.emit(text)
            except Exception as e:
                print("WING PAY 크롤링 오류:", e)
                self.automation_complete.emit("Automation Error")
            finally:
                self.otp_hide.emit(self.config['site_name'])
                time.sleep(15)
                driver.quit()
            return

        try:
            driver = create_chrome_driver(non_headless_options)
            if not driver:
                self.automation_complete.emit("Driver Init Failed")
                return
            driver.maximize_window()
            while True:
                self.perform_login(driver)
                self.perform_post_login_actions(driver)
                final_data = self.final_crawl(driver)
                print(f"[{self.config['site_name']}] 최종 크롤링 데이터: {final_data}")
                self.automation_complete.emit(final_data)
                time.sleep(15)
        except Exception as e:
            print(f"SiteAutomationThread ({self.config['site_name']}) 오류:", e)
            self.automation_complete.emit("Automation Error")
        finally:
            self.otp_hide.emit(self.config['site_name'])
            driver.quit()

    def perform_login(self, driver):
        driver.get(self.config['login_url'])
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config['login_id_xpath'])))
        time.sleep(15)
        id_field = driver.find_element(By.XPATH, self.config['login_id_xpath'])
        id_field.clear()
        id_field.send_keys(self.config['login_id'])
        pw_field = driver.find_element(By.XPATH, self.config['login_pw_xpath'])
        pw_field.clear()
        pw_field.send_keys(self.config['login_pw'])
        driver.find_element(By.XPATH, self.config['login_button_xpath']).click()
        time.sleep(15)

    def handle_otp(self, driver):
        if self.config.get('otp_xpath', "").strip():
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config['otp_xpath'])))
            self.otp_ready.emit(self.config['site_name'])
            while self.config.get('otp_value', '') == '':
                time.sleep(0.5)
            otp_to_send = self.config.get('otp_value', '')
            if otp_to_send:
                otp_field = driver.find_element(By.XPATH, self.config['otp_xpath'])
                otp_field.clear()
                otp_field.send_keys(otp_to_send + Keys.ENTER)
                self.config['otp_value'] = ''
                time.sleep(15)
        else:
            pass

    def perform_post_login_actions(self, driver):
        driver.get(self.config['post_login_url'])
        if 'post_login_actions' in self.config:
            actions = self.config['post_login_actions']
            for action in actions:
                action_type = action.get('action')
                xpath = action.get('xpath')
                delay = action.get('delay', 1)
                WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, xpath)))
                if action_type == 'click':
                    driver.find_element(By.XPATH, xpath).click()
                elif action_type == 'input':
                    input_value = action.get('value', '')
                    elem = driver.find_element(By.XPATH, xpath)
                    elem.clear()
                    elem.send_keys(input_value)
                time.sleep(delay)
        else:
            pass

    def final_crawl(self, driver):
        final_elem = driver.find_element(By.XPATH, self.config['final_crawl_xpath'])
        return final_elem.text

##############################################
# 사이트 설정 (개별 분기 및 OTP 조건 추가)
##############################################
site_configs = {
    "B.C": {
        'login_url': 'https://www.accounts-bc.com/signin',
        'login_id': 'juyeonglee911029@gmail.com',
        'login_pw': '12Qwaszx!@',
        'login_id_xpath': '/html/body/div[1]/ul/li[2]/div/ul/li[2]/div[1]/div/input',
        'login_pw_xpath': '/html/body/div[1]/ul/li[2]/div/ul/li[2]/div[2]/div/div/input',
        'login_button_xpath': '/html/body/div[1]/ul/li[2]/div/ul/li[3]/button',
        'otp_xpath': '/html/body/div[1]/ul/li[2]/div/ul/li[2]/div/div[1]/div/input',
        'post_login_url': 'https://scoutdata.feedconstruct.com/',
        'click_xpath1': '', 'click_xpath2': '', 'click_xpath3': '',
        'final_crawl_xpath': '/html/body/app-root/app-app/div/div[2]/app-game-section/div/div/div[2]/div/div[1]/div/div/mat-form-field/div[1]/div[2]/div[1]/input',
        'otp_value': '',
        'site_name': 'B.C'
    },
    "VECT PAY": {
        'login_url': 'https://kba-europe.com/login/?redirect_to=https%3A%2F%2Fkba-europe.com',
        'login_id': '아이디에요',
        'login_pw': '비번이에요',
        'login_id_xpath': '/html/body/div[1]/div/div[3]/div[1]/div/div/div[3]/div[2]/div/div/div/div/div/div/form/div/div[1]/div/div[1]/div[1]/input',
        'login_pw_xpath': '/html/body/div[1]/div/div[3]/div[1]/div/div/div[3]/div[2]/div/div/div/div/div/div/form/div/div[1]/div/div[1]/div[2]/input',
        'login_button_xpath': '/html/body/div[1]/div/div[3]/div[1]/div/div/div[3]/div[2]/div/div/div/div/div/div/form/div/div[1]/div/div[2]/button',
        'otp_xpath': '/html/body/div[1]/div/div[3]/div[1]/div/div/div[3]/div[2]/div/div/div/div/div/div[2]/form/div/div[1]/div/div[1]/div[1]/input',
        'post_login_url': 'https://www.winglobalpay.com/',
        'click_xpath1': '/html/body/div[1]/div[1]/header/button[1]',
        'click_xpath2': '/html/body/div[1]/div[2]/nav/ul/li[2]/a',
        'click_xpath3': '/html/body/div[1]/div[2]/nav/ul/li[2]/ul/li[1]/a',
        'final_crawl_xpath': '/html/body/div[1]/div/div[3]/div[2]/div/div/div/div/div/div/div[2]/ul/li[3]',  # 입력창에 "안녕 잘입력되고 있어 굿바이" 입력
        'otp_value': '',
        'site_name': 'VECT PAY'
    },
    "WING PAY": {
        'login_url': 'https://nid.naver.com/nidlogin.login?mode=form&url=https://www.naver.com/',
        'login_id': '아이디입니다',
        'login_pw': '비밀번호입니다',
        'login_id_xpath': '/html/body/div[1]/div[2]/div/div[1]/form/ul/li/div/div[1]/div/div[1]/input',
        'login_pw_xpath': '/html/body/div[1]/div[2]/div/div[1]/form/ul/li/div/div[1]/div/div[2]/input',
        'login_button_xpath': '/html/body/div[1]/div[2]/div/div[1]/form/ul/li/div/div[11]/button',
        'otp_xpath': '', 
        'post_login_url': '',
        'click_xpath1': '', 'click_xpath2': '', 'click_xpath3': '',
        'final_crawl_xpath': '/html/body/div[1]/div[1]/div[2]/div/div/div[4]/div[1]/div/div[1]/div/ul/li[1]/a/span',
        'otp_value': '',
        'site_name': 'WING PAY'
    },
    "개인장 출금": {
        'login_url': 'https://www.pushbullet.com/1',
        'login_id': 'your_gein_id',
        'login_pw': 'your_gein_pw',
        'login_id_xpath': 'XPath_GEIN_LOGIN_ID',
        'login_pw_xpath': 'XPath_GEIN_LOGIN_PW',
        'login_button_xpath': 'XPath_GEIN_LOGIN_BTN',
        'otp_xpath': '', 
        'post_login_url': 'https://www.pushbullet.com/1',
        'click_xpath1': 'XPath_GEIN_CLICK1',
        'click_xpath2': 'XPath_GEIN_CLICK2',
        'click_xpath3': 'XPath_GEIN_CLICK3',
        'final_crawl_xpath': 'XPath_GEIN_FINAL',
        'otp_value': '',
        'site_name': '개인장 출금'
    },
    "개인장 잔액": {
        'login_url': 'https://www.pushbullet.com/1',
        'login_id': 'your_gein_id',
        'login_pw': 'your_gein_pw',
        'login_id_xpath': 'XPath_GEIN_LOGIN_ID',
        'login_pw_xpath': 'XPath_GEIN_LOGIN_PW',
        'login_button_xpath': 'XPath_GEIN_LOGIN_BTN',
        'otp_xpath': '', 
        'post_login_url': 'https://www.pushbullet.com/1',
        'click_xpath1': 'XPath_GEIN_CLICK1',
        'click_xpath2': 'XPath_GEIN_CLICK2',
        'click_xpath3': 'XPath_GEIN_CLICK3',
        'final_crawl_xpath': 'XPath_GEIN_FINAL',
        'otp_value': '',
        'site_name': '개인장 잔액'
    },
    "LEVEL 장": {
        'login_url': 'https://www.pushbullet.com/1',
        'login_id': 'your_level_id',
        'login_pw': 'your_level_pw',
        'login_id_xpath': 'XPath_LEVEL_LOGIN_ID',
        'login_pw_xpath': 'XPath_LEVEL_LOGIN_PW',
        'login_button_xpath': 'XPath_LEVEL_LOGIN_BTN',
        'otp_xpath': '',
        'post_login_url': 'https://www.netflix.com/dashboard',
        'click_xpath1': 'XPath_LEVEL_CLICK1',
        'click_xpath2': 'XPath_LEVEL_CLICK2',
        'click_xpath3': 'XPath_LEVEL_CLICK3',
        'final_crawl_xpath': 'XPath_LEVEL_FINAL',
        'otp_value': '',
        'site_name': 'LEVEL 장'
    }
}

##############################################
# Login 화면
##############################################
class LoginWidget(QWidget):
    login_success = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    def setup_ui(self):
        self.setMinimumSize(300,150)
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        form_group = QGroupBox("")
        form_group.setStyleSheet("background-color: #FFFFFF; color: #333333; border: none;")
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("아이디")
        self.username_edit.setFixedHeight(30)
        self.username_edit.setText("EXTA")
        self.username_edit.setStyleSheet("font-size: 10pt; color: #333333; background-color: #D3D3D3; border: none;")
        self.username_edit.setFixedWidth(120)
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("비밀번호")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setFixedHeight(30)
        self.password_edit.setText("papa")
        self.password_edit.setStyleSheet("font-size: 10pt; color: #333333; background-color: #D3D3D3; border: none;")
        self.password_edit.setFixedWidth(120)
        form_layout.addRow("ID :", self.username_edit)
        form_layout.addRow("Password :", self.password_edit)
        form_group.setLayout(form_layout)
        main_layout.addWidget(form_group, alignment=Qt.AlignCenter)
        # 수정: 로그인 버튼을 AnimatedButton으로 교체하여 호버 효과 적용
        self.login_button = AnimatedButton("로그인")
        self.login_button.clicked.connect(self.handle_login)
        self.login_button.setFixedHeight(30)
        self.login_button.setFixedWidth(120)
        main_layout.addWidget(self.login_button, alignment=Qt.AlignCenter)
        self.success_label = QLabel("로그인 성공")
        self.success_label.setAlignment(Qt.AlignCenter)
        self.success_label.setStyleSheet("color: green; font-size: 12pt;")
        self.success_label.setVisible(False)
        self.success_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        main_layout.addWidget(self.success_label, alignment=Qt.AlignCenter)
    def handle_login(self):
        if self.username_edit.text().strip() == "EXTA" and self.password_edit.text().strip() == "papa":
            self.show_success_message()
        else:
            QMessageBox.warning(self, "오류", "아이디 또는 비밀번호가 올바르지 않습니다.")
    def show_success_message(self):
        self.success_label.setVisible(True)
        self.success_label.setGraphicsEffect(None)
        QTimer.singleShot(2000, self.fade_out_success_message)
    def fade_out_success_message(self):
        effect = QGraphicsOpacityEffect(self.success_label)
        self.success_label.setGraphicsEffect(effect)
        self.anim = QPropertyAnimation(effect, b"opacity")
        self.anim.setDuration(1000)
        self.anim.setStartValue(1)
        self.anim.setEndValue(0)
        self.anim.finished.connect(self.on_fade_finished)
        self.anim.start()
    def on_fade_finished(self):
        self.login_success.emit("EXTA")

##############################################
# 메인 인터페이스 (2열 레이아웃 적용)
##############################################
class MainInterfaceWidget(QWidget):
    def __init__(self, login_id, parent=None):
        super().__init__(parent)
        self.login_id = login_id
        self.last_success_time = ""
        self.automation_on_time = None
        self.modify_buttons = {}
        self.fetch_edits = {}
        self.otp_inputs = {}   # OTP 위젯은 기본적으로 숨김 처리
        self.send_buttons = {}
        self.error_msg_labels = {}
        self.error_status = {}
        self.bottom_info = QLabel("")
        self.last_success_label = QLabel("")
        # 정산 시각(최종 정상 시각)을 15pt, 굵게, 파란색으로 표시
        self.last_success_label.setStyleSheet("font-size: 15pt; color: blue; font-weight: bold;")
        self.result_msg_label = QLabel("")
        self.result_msg_label.setVisible(False)
        self.configs = site_configs
        self.setup_ui()
        self.start_timer()
        QTimer.singleShot(5000, self.start_site_automation_all)
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(5,5,5,5)
        title = QLabel("자동 정산 시스템")
        title.setStyleSheet("font-size: 13pt; color: #0066CC; border: none;")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hbox = QHBoxLayout()
        # 왼쪽 열: B.C, 합계, 정산 결과
        left_vbox = QVBoxLayout()
        left_grid = QGridLayout()
        left_grid.setSpacing(3)
        left_grid.addWidget(QLabel("B.C"), 0, 0)
        # 수정: 더블클릭으로 수정되지 않도록 NumberLineEdit 사용
        field_bc = NumberLineEdit()
        field_bc.setReadOnly(True)
        field_bc.setPlaceholderText("자동 업데이트 / 수동 입력")
        field_bc.setAlignment(Qt.AlignCenter)
        field_bc.setStyleSheet("font-size: 11pt; color: white; background-color: black; border: none;")
        left_grid.addWidget(field_bc, 0, 1)
        self.fetch_edits["B.C"] = field_bc
        btn_bc = AnimatedButton("수정")
        btn_bc.setFixedSize(60,30)
        btn_bc.clicked.connect(lambda checked, s="B.C": self.modify_auto_update(s))
        left_grid.addWidget(btn_bc, 0, 2)
        self.modify_buttons["B.C"] = btn_bc
        err_bc = QLabel("")
        err_bc.setFixedWidth(100)
        err_bc.setStyleSheet("color: orange; font-size: 10pt;")
        err_bc.setVisible(False)
        left_grid.addWidget(err_bc, 0, 3)
        self.error_msg_labels["B.C"] = err_bc
        if self.configs["B.C"].get("otp_xpath", "").strip():
            otp_bc = QLineEdit()
            otp_bc.setMaxLength(6)
            otp_bc.setPlaceholderText("OTP 입력")
            otp_bc.setAlignment(Qt.AlignCenter)
            otp_bc.setStyleSheet("font-size: 11pt; color: white; background-color: black; border: none;")
            otp_bc.setFixedSize(100,30)
            otp_bc.setVisible(False)
            left_grid.addWidget(otp_bc, 0, 4)
            self.otp_inputs["B.C"] = otp_bc
            send_bc = AnimatedButton("전송")
            send_bc.setFixedSize(60,30)
            send_bc.setStyleSheet("background-color: transparent; border: none; font-size: 13pt; color: #0066CC;")
            send_bc.setVisible(False)
            send_bc.clicked.connect(lambda checked, s="B.C": self.send_otp(s))
            left_grid.addWidget(send_bc, 0, 5)
            self.send_buttons["B.C"] = send_bc
        left_grid.addWidget(QLabel("합계"), 1, 0)
        sum_field = NumberLineEdit()
        sum_field.setReadOnly(True)
        sum_field.setText("0")
        sum_field.setAlignment(Qt.AlignCenter)
        sum_field.setStyleSheet("font-size: 11pt; color: white; background-color: black; border: none;")
        left_grid.addWidget(sum_field, 1, 1)
        self.sum_edit = sum_field
        left_grid.addWidget(QLabel("정산 결과"), 2, 0)
        settlement_field = NumberLineEdit()
        settlement_field.setReadOnly(True)
        settlement_field.setText("0")
        settlement_field.setAlignment(Qt.AlignCenter)
        settlement_field.setStyleSheet("font-size: 11pt; color: white; background-color: black; border: none;")
        left_grid.addWidget(settlement_field, 2, 1)
        self.settlement_edit = settlement_field
        left_grid.addWidget(self.result_msg_label, 3, 0, 1, 3)
        left_grid.addWidget(self.last_success_label, 4, 0, 1, 3)
        left_vbox.addLayout(left_grid)
        hbox.addLayout(left_vbox)
        # 오른쪽 열: VECT PAY, WING PAY, LEVEL 장, 개인장 출금, 개인장 잔액
        right_vbox = QVBoxLayout()
        right_grid = QGridLayout()
        right_grid.setSpacing(3)
        sites_right = ["VECT PAY", "WING PAY", "LEVEL 장", "개인장 출금", "개인장 잔액"]
        row = 0
        for site in sites_right:
            right_grid.addWidget(QLabel(site), row, 0)
            # 수정: NumberLineEdit로 생성하여 더블클릭 편집 방지
            field = NumberLineEdit()
            field.setReadOnly(True)
            field.setPlaceholderText("자동 업데이트 / 수동 입력")
            field.setAlignment(Qt.AlignCenter)
            field.setStyleSheet("font-size: 11pt; color: white; background-color: black; border: none;")
            right_grid.addWidget(field, row, 1)
            self.fetch_edits[site] = field
            btn = AnimatedButton("수정")
            btn.setFixedSize(60,30)
            btn.clicked.connect(lambda checked, s=site: self.modify_auto_update(s))
            right_grid.addWidget(btn, row, 2)
            self.modify_buttons[site] = btn
            if self.configs[site].get("otp_xpath", "").strip():
                otp_in = QLineEdit()
                otp_in.setMaxLength(6)
                otp_in.setPlaceholderText("OTP 입력")
                otp_in.setAlignment(Qt.AlignCenter)
                otp_in.setStyleSheet("font-size: 11pt; color: white; background-color: black; border: none;")
                otp_in.setFixedSize(100,30)
                otp_in.setVisible(False)
                right_grid.addWidget(otp_in, row, 3)
                self.otp_inputs[site] = otp_in
                send_btn = AnimatedButton("전송")
                send_btn.setFixedSize(60,30)
                send_btn.setStyleSheet("background-color: transparent; border: none; font-size: 13pt; color: #0066CC;")
                send_btn.setVisible(False)
                send_btn.clicked.connect(lambda checked, s=site: self.send_otp(s))
                right_grid.addWidget(send_btn, row, 4)
                self.send_buttons[site] = send_btn
            row += 1
        right_vbox.addLayout(right_grid)
        hbox.addLayout(right_vbox)
        main_layout.addLayout(hbox)
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self.bottom_info = QLabel(f"사용자: {self.login_id}    {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
        self.bottom_info.setStyleSheet("font-size: 12pt; color: #333333;")
        bottom_layout.addWidget(self.bottom_info)
        bottom_layout.addStretch()
        main_layout.addLayout(bottom_layout)
        self.setLayout(main_layout)
    def modify_auto_update(self, site):
        field = self.fetch_edits.get(site)
        btn = self.modify_buttons.get(site)
        if field is None or btn is None:
            return
        if field.isReadOnly():
            # 수정 버튼 클릭 -> 편집 가능 상태로 전환
            field.setReadOnly(False)
            field.selectAll()  # 전체 텍스트 자동 선택
            btn.setText("완료")
            btn.setStyleSheet("background-color: transparent; border: none; font-size: 13pt; color: #00FF00;")
        else:
            # 완료 버튼 클릭 -> 편집 불가 상태로 전환하며 애니메이션 및 배경색 변경
            field.setReadOnly(True)
            effect = QGraphicsOpacityEffect(field)
            field.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b"opacity")
            anim.setDuration(500)
            anim.setStartValue(1)
            anim.setEndValue(0.7)
            anim.start()
            field.setStyleSheet("font-size: 11pt; color: white; background-color: grey; border: none;")
            btn.setText("수정")
            btn.setStyleSheet("background-color: transparent; border: none; font-size: 13pt; color: #0066CC;")
            self.calculate_settlement()
    def modify_personal_balance(self):
        field = self.fetch_edits.get("개인장 잔액")
        btn = self.modify_buttons.get("개인장 잔액")
        if field is None or btn is None:
            return
        if field.isReadOnly():
            field.setReadOnly(False)
            field.selectAll()
            btn.setText("완료")
            btn.setStyleSheet("background-color: transparent; border: none; font-size: 13pt; color: #00FF00;")
        else:
            field.setReadOnly(True)
            btn.setText("수정")
            btn.setStyleSheet("background-color: transparent; border: none; font-size: 13pt; color: #0066CC;")
    def send_otp(self, site):
        otp_val = self.otp_inputs[site].text() if self.otp_inputs.get(site) else ""
        self.configs[site]['otp_value'] = otp_val
        print(f"{site} OTP 전송: {otp_val}")
        if self.otp_inputs.get(site):
            self.otp_inputs[site].clear()
        self.hide_otp(site)
    def calculate_settlement(self):
        try:
            bc_val = float(re.sub(r"[^\d\.]", "", self.fetch_edits.get("B.C").text()))
        except:
            bc_val = 0.0
        total_other = 0.0
        for site in ["VECT PAY", "WING PAY", "LEVEL 장", "개인장 출금", "개인장 잔액"]:
            try:
                val = float(re.sub(r"[^\d\.]", "", self.fetch_edits.get(site).text()))
            except:
                val = 0.0
            total_other += val
        self.sum_edit.setText(format_number(str(total_other)))
        diff = bc_val - total_other
        if diff == 0:
            # 정상일 경우 모든 글씨 초록색, 정산 시각은 15pt, 굵게, 파란색 유지
            self.settlement_edit.setText(f"{format_number(str(diff))} (정상)")
            self.settlement_edit.setStyleSheet("font-size: 15pt; color: green; background-color: black; border: none;")
            self.result_msg_label.setText("")
            self.last_success_label.setText(f"최종 정상 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.last_success_label.setStyleSheet("font-size: 15pt; color: blue; font-weight: bold;")
        else:
            self.settlement_edit.setText(f"{format_number(str(diff))} (비정상)")
            self.settlement_edit.setStyleSheet("font-size: 11pt; color: red; background-color: black; border: none;")
            msg = "증복입금 혹은 오승인 확인 요망." if bc_val > total_other else "입금 후 미신청 또는 핑돈 확인 요망."
            if msg == "입금 후 미신청 또는 핑돈 확인 요망.":
                self.result_msg_label.setStyleSheet("font-size: 15pt; color: red; font-weight: bold;")
            else:
                self.result_msg_label.setStyleSheet("font-size: 15pt; color: red;")
            self.result_msg_label.setText(msg)
            self.result_msg_label.setVisible(True)
    def update_error_label(self, site, error_text):
        if site in self.error_msg_labels:
            lbl = self.error_msg_labels[site]
            lbl.setText("X")
            lbl.setVisible(True)
            QTimer.singleShot(2000, lambda: lbl.setVisible(False))
    def start_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.update_time()
    def update_time(self):
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        self.bottom_info.setText(f"사용자: {self.login_id}    {current_time}")
    def start_site_automation_all(self):
        self.configs = site_configs
        self.error_status = {site: False for site in self.configs.keys()}
        self.site_auto_threads = []
        for config in self.configs.values():
            thread = SiteAutomationThread(config)
            thread.automation_complete.connect(functools.partial(self.update_site_field, config['site_name']))
            thread.otp_ready.connect(functools.partial(self.animate_otp, config['site_name']))
            thread.otp_hide.connect(functools.partial(self.hide_otp, config['site_name']))
            thread.start()
            self.site_auto_threads.append(thread)
    def update_site_field(self, site, value):
        field = self.fetch_edits.get(site)
        if value == "Automation Error":
            self.update_error_label(site, "Automation Error")
        else:
            if not value.strip():
                value = "0"
            if field.isReadOnly():
                field.setText(format_number(value))
                field.setStyleSheet("font-size: 11pt; color: red; background-color: black; border: none;")
        self.calculate_settlement()
    def animate_otp(self, site):
        if site in self.configs and self.configs[site].get("otp_xpath", "").strip():
            if site in self.otp_inputs and self.otp_inputs[site] is not None:
                anim = QPropertyAnimation(self.otp_inputs[site], b"windowOpacity")
                anim.setDuration(2000)
                anim.setStartValue(0)
                anim.setEndValue(1)
                anim.start()
                self.otp_inputs[site].setVisible(True)
                anim2 = QPropertyAnimation(self.send_buttons[site], b"windowOpacity")
                anim2.setDuration(2000)
                anim2.setStartValue(0)
                anim2.setEndValue(1)
                anim2.start()
                self.send_buttons[site].setVisible(True)
            else:
                otp_in = QLineEdit()
                otp_in.setMaxLength(6)
                otp_in.setPlaceholderText("OTP 입력")
                otp_in.setAlignment(Qt.AlignCenter)
                otp_in.setStyleSheet("font-size: 11pt; color: white; background-color: black; border: none;")
                otp_in.setFixedSize(100,30)
                self.otp_inputs[site] = otp_in
                send_btn = AnimatedButton("전송")
                send_btn.setFixedSize(60,30)
                send_btn.clicked.connect(lambda checked, s=site: self.send_otp(s))
                self.send_buttons[site] = send_btn
                otp_in.setVisible(True)
                send_btn.setVisible(True)
    def hide_otp(self, site):
        if site in self.otp_inputs and self.otp_inputs[site] is not None:
            self.otp_inputs[site].setVisible(False)
        if site in self.send_buttons and self.send_buttons[site] is not None:
            self.send_buttons[site].setVisible(False)
    def open_excel_file(self):
        pass

##############################################
# MainWindow
##############################################
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("실시간 정산 시스템")
        self.resize(200,200)
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        self.login_widget = LoginWidget()
        self.login_widget.login_success.connect(self.on_login_success)
        self.stacked_widget.addWidget(self.login_widget)
    def on_login_success(self, login_id):
        print("로그인 성공:", login_id)
        self.main_interface = MainInterfaceWidget(login_id)
        self.stacked_widget.addWidget(self.main_interface)
        self.stacked_widget.setCurrentWidget(self.main_interface)
        print("메인 인터페이스로 전환됨")
    def closeEvent(self, event):
        try:
            if hasattr(self, 'main_interface'):
                del self.main_interface
        except Exception as e:
            print("종료 시 오류:", e)
        event.accept()

##############################################
# 종료 처리 함수
##############################################
def cleanup():
    print("프로그램 종료, 모든 브라우저 종료")
atexit.register(cleanup)

##############################################
# 메인 함수
##############################################
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet("""
* {
    font-family: 'Malgun Gothic', sans-serif;
}
QWidget {
    background-color: #F0F0F0;
    color: #333333;
}
QGroupBox {
    background-color: #FFFFFF;
    border: none;
}
QLineEdit {
    background-color: black;
    border: none;
    border-radius: 5px;
    padding: 6px;
    font-size: 11pt;
    color: white;
}
QPushButton {
    background-color: #E0E0E0;
    border: none;
    border-radius: 5px;
    padding: 8px 16px;
    font-size: 9pt;
    color: #333333;
}
QPushButton:hover {
    background-color: #D0D0D0;
}
QCheckBox {
    font-size: 12pt;
    color: #333333;
}
QTextEdit {
    background-color: #D3D3D3;
    border: none;
    font-size: 11pt;
    color: #333333;
}
""")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()




####################################################################################################
# FINAL_SETTLEMENT_SYSTEM.PY (최종 수정본 v7.3.9)
# 제작자: ChatGPT
# 작성일: 2025-02-27
#
# [변경 사항]
# 1. 모든 텍스트 입력창은 5초 단위로 업데이트되며, 값이 없으면 "0"으로 표시됨.
# 2. 자동 데이터는 빨간색, 수동 입력 시 흰색으로 표시됨.
# 3. GUI는 5행×2열 그리드 레이아웃으로 구성됨.
#    - 행0: 좌측 – "B.C" (자동 업데이트 필드, 수정 버튼, config의 otp_xpath가 있을 경우에만 OTP 입력창/전송 버튼),
#            우측 – "VECT PAY"
#    - 행1: 좌측 – "합계", 우측 – "WING PAY"
#    - 행2: 좌측 – "정산 결과", 우측 – "LEVEL 장"
#    - 행3: 좌측 – "중복 승인" (수동 입력), 우측 – "개인장 출금"
#    - 행4: 좌측 – "입금 후 미신청" (수동 입력), 우측 – "개인장 잔액"
#    하단에 결과 메시지와 최종 정상 시각이 전체 너비로 배치됨.
# 4. 수정/전송 버튼은 AnimatedButton 클래스로 구현되며, 수정 버튼 클릭 시 입력창이 편집 가능해지고,
#    완료 버튼 클릭 시 애니메이션 효과와 함께 읽기전용 및 배경색 변경으로 잠금 상태를 표시함.
# 5. 모든 자동/수동 입력창은 Ctrl+C & Ctrl+V 단축키로 복사/붙여넣기 기능을 지원함.
# 6. OTP 입력창과 전송 버튼은 config의 otp_xpath 정보가 있을 때만 GUI에 노출됨.
# 7. VECT PAY는 최종 크롤링 시, final_crawl_xpath에서 26번째 글자부터 추출한 후 숫자만 남기고 천단위 콤마 포맷 적용.
# 8. 정산 결과는 (B.C + 중복 승인) – [(WING PAY + VECT PAY + LEVEL 장 + 개인장 출금 + 개인장 잔액) – (입금 후 미신청)]
#    수식으로 계산됨.
####################################################################################################

import sys, os, time, re, atexit, subprocess, functools
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel,
    QMainWindow, QMessageBox, QHBoxLayout, QStackedWidget, QGridLayout, QGroupBox, QGraphicsOpacityEffect
)
from PyQt5.QtCore import QRegExp, Qt, QTimer, QPropertyAnimation, pyqtSignal, QThread, QVariantAnimation
from PyQt5.QtGui import QRegExpValidator, QColor, QGuiApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

##############################################
# AnimatedButton: 수정/전송 버튼 (호버 효과 및 스타일)
##############################################
class AnimatedButton(QPushButton):
    def __init__(self, text=""):
        super().__init__(text)
        self.setStyleSheet("background-color: #2196F3; border: none; border-radius: 10px; font-size: 13pt; color: white;")
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(500)
        self.anim.valueChanged.connect(self.on_value_changed)
    def on_value_changed(self, value):
        base_color = QColor("#2196F3")
        hover_color = QColor("#0D47A1")
        r = base_color.red() + (hover_color.red() - base_color.red()) * value
        g = base_color.green() + (hover_color.green() - base_color.green()) * value
        b = base_color.blue() + (hover_color.blue() - base_color.blue()) * value
        new_color = QColor(int(r), int(g), int(b))
        self.setStyleSheet(f"background-color: {new_color.name()}; border: none; border-radius: 10px; font-size: 13pt; color: white;")
    def enterEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()
        super().enterEvent(event)
    def leaveEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.start()
        super().leaveEvent(event)

##############################################
# NumberLineEdit (자동/수동 입력창, 복사/붙여넣기 지원)
##############################################
class NumberLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self.setValidator(QRegExpValidator(QRegExp("^[0-9]{0,11}$"), self))
        self.textChanged.connect(self.formatText)
    def formatText(self, text):
        self.blockSignals(True)
        digits = text.replace(",", "")
        if digits == "":
            self.blockSignals(False)
            return
        try:
            num = int(digits)
            formatted = f"{num:,}"
            self.setText(formatted)
        except Exception:
            pass
        self.blockSignals(False)
    def keyPressEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_C:
                self.copy()
                return
            elif event.key() == Qt.Key_V:
                self.paste()
                return
        super().keyPressEvent(event)

##############################################
# create_chrome_driver 및 옵션 설정
##############################################
def create_chrome_driver(options, retries=3):
    for i in range(retries):
        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            return driver
        except Exception as e:
            print(f"Chrome 드라이버 초기화 오류 (시도 {i+1}/{retries}): {e}")
            time.sleep(2)
    return None

non_headless_options = webdriver.ChromeOptions()

##############################################
# 헬퍼 함수: format_number
##############################################
def format_number(value):
    if not value.strip():
        return "0"
    try:
        num = float(value.replace(",", "").strip())
        return f"{int(num):,}"
    except Exception:
        return value

##############################################
# 사이트별 크롤링 스레드
##############################################
class SiteAutomationThread(QThread):
    automation_complete = pyqtSignal(str)
    otp_ready = pyqtSignal(str)
    otp_hide = pyqtSignal(str)
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
    def run(self):
        if self.config["site_name"] == "VECT PAY":
            try:
                driver = create_chrome_driver(non_headless_options)
                if not driver:
                    self.automation_complete.emit("Driver Init Failed")
                    return
                driver.maximize_window()
                driver.get(self.config["login_url"])
                WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config["login_id_xpath"])))
                time.sleep(15)
                driver.find_element(By.XPATH, self.config["login_id_xpath"]).clear()
                driver.find_element(By.XPATH, self.config["login_id_xpath"]).send_keys(self.config["login_id"])
                driver.find_element(By.XPATH, self.config["login_pw_xpath"]).clear()
                driver.find_element(By.XPATH, self.config["login_pw_xpath"]).send_keys(self.config["login_pw"])
                driver.find_element(By.XPATH, self.config["login_button_xpath"]).click()
                time.sleep(15)
                if self.config.get("otp_xpath", "").strip():
                    try:
                        otp_field = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config["otp_xpath"])))
                        self.otp_ready.emit(self.config["site_name"])
                        while self.config.get("otp_value", "") == "":
                            time.sleep(0.5)
                        otp_to_send = self.config.get("otp_value", "")
                        if otp_to_send:
                            otp_field.clear()
                            otp_field.send_keys(otp_to_send + Keys.ENTER)
                            self.config["otp_value"] = ""
                            time.sleep(15)
                    except Exception as e:
                        print("VECT PAY OTP 요소 미발견:", e)
                time.sleep(15)
                while True:
                    time.sleep(3)
                    driver.refresh()
                    elem = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config["final_crawl_xpath"])))
                    raw_text = elem.text
                    extracted_text = raw_text[25:] if len(raw_text) >= 26 else ""
                    digits_only = re.sub(r"\D", "", extracted_text)
                    if not digits_only:
                        digits_only = "0"
                    formatted_number = f"{int(digits_only):,}"
                    self.automation_complete.emit(formatted_number)
            except Exception as e:
                print("VECT PAY 크롤링 오류:", e)
                self.automation_complete.emit("Automation Error")
            finally:
                time.sleep(15)
                driver.quit()
            return
        elif self.config["site_name"] == "B.C":
            try:
                driver = create_chrome_driver(non_headless_options)
                if not driver:
                    self.automation_complete.emit("Driver Init Failed")
                    return
                driver.maximize_window()
                driver.get(self.config["login_url"])
                WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config["login_id_xpath"])))
                time.sleep(15)
                driver.find_element(By.XPATH, self.config["login_id_xpath"]).clear()
                driver.find_element(By.XPATH, self.config["login_id_xpath"]).send_keys(self.config["login_id"])
                driver.find_element(By.XPATH, self.config["login_pw_xpath"]).clear()
                driver.find_element(By.XPATH, self.config["login_pw_xpath"]).send_keys(self.config["login_pw"])
                driver.find_element(By.XPATH, self.config["login_button_xpath"]).click()
                time.sleep(15)
                if self.config.get("otp_xpath", "").strip():
                    try:
                        otp_field = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config["otp_xpath"])))
                        self.otp_ready.emit(self.config["site_name"])
                        while self.config.get("otp_value", "") == "":
                            time.sleep(0.5)
                        otp_to_send = self.config.get("otp_value", "")
                        if otp_to_send:
                            otp_field.clear()
                            otp_field.send_keys(otp_to_send + Keys.ENTER)
                            self.config["otp_value"] = ""
                            time.sleep(15)
                    except Exception as e:
                        print("B.C OTP 요소 미발견:", e)
                time.sleep(15)
                driver.get(self.config["post_login_url"])
                while True:
                    time.sleep(15)
                    driver.refresh()
                    elem = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config["final_crawl_xpath"])))
                    text = elem.text
                    if "." in text:
                        text = text.split(".")[0]
                    self.automation_complete.emit(text)
            except Exception as e:
                print("B.C 크롤링 오류:", e)
                self.automation_complete.emit("Automation Error")
            finally:
                self.otp_hide.emit(self.config["site_name"])
                time.sleep(15)
                driver.quit()
            return
        elif self.config["site_name"] == "WING PAY":
            try:
                driver = create_chrome_driver(non_headless_options)
                if not driver:
                    self.automation_complete.emit("Driver Init Failed")
                    return
                driver.maximize_window()
                driver.get(self.config["login_url"])
                WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config["login_id_xpath"])))
                time.sleep(20)
                driver.find_element(By.XPATH, self.config["login_id_xpath"]).clear()
                driver.find_element(By.XPATH, self.config["login_id_xpath"]).send_keys(self.config["login_id"])
                driver.find_element(By.XPATH, self.config["login_pw_xpath"]).clear()
                driver.find_element(By.XPATH, self.config["login_pw_xpath"]).send_keys(self.config["login_pw"])
                driver.find_element(By.XPATH, self.config["login_button_xpath"]).click()
                time.sleep(15)
                driver.get("https://m.stock.naver.com/worldstock/home/USA/marketValue/NASDAQ")
                while True:
                    time.sleep(15)
                    driver.refresh()
                    elem = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config["final_crawl_xpath"])))
                    text = elem.text
                    if "." in text:
                        text = text.split(".")[0]
                    self.automation_complete.emit(text)
            except Exception as e:
                print("WING PAY 크롤링 오류:", e)
                self.automation_complete.emit("Automation Error")
            finally:
                self.otp_hide.emit(self.config["site_name"])
                time.sleep(15)
                driver.quit()
            return
        try:
            driver = create_chrome_driver(non_headless_options)
            if not driver:
                self.automation_complete.emit("Driver Init Failed")
                return
            driver.maximize_window()
            while True:
                self.perform_login(driver)
                self.perform_post_login_actions(driver)
                final_data = self.final_crawl(driver)
                print(f"[{self.config['site_name']}] 최종 크롤링 데이터: {final_data}")
                self.automation_complete.emit(final_data)
                time.sleep(15)
        except Exception as e:
            print(f"SiteAutomationThread ({self.config['site_name']}) 오류:", e)
            self.automation_complete.emit("Automation Error")
        finally:
            self.otp_hide.emit(self.config["site_name"])
            driver.quit()

    def perform_login(self, driver):
        driver.get(self.config["login_url"])
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config["login_id_xpath"])))
        time.sleep(15)
        id_field = driver.find_element(By.XPATH, self.config["login_id_xpath"])
        id_field.clear()
        id_field.send_keys(self.config["login_id"])
        pw_field = driver.find_element(By.XPATH, self.config["login_pw_xpath"])
        pw_field.clear()
        pw_field.send_keys(self.config["login_pw"])
        driver.find_element(By.XPATH, self.config["login_button_xpath"]).click()
        time.sleep(15)

    def handle_otp(self, driver):
        if self.config.get("otp_xpath", "").strip():
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, self.config["otp_xpath"])))
            self.otp_ready.emit(self.config["site_name"])
            while self.config.get("otp_value", "") == "":
                time.sleep(0.5)
            otp_to_send = self.config.get("otp_value", "")
            if otp_to_send:
                otp_field = driver.find_element(By.XPATH, self.config["otp_xpath"])
                otp_field.clear()
                otp_field.send_keys(otp_to_send + Keys.ENTER)
                self.config["otp_value"] = ""
                time.sleep(15)
        else:
            pass

    def perform_post_login_actions(self, driver):
        driver.get(self.config["post_login_url"])
        if "post_login_actions" in self.config:
            actions = self.config["post_login_actions"]
            for action in actions:
                action_type = action.get("action")
                xpath = action.get("xpath")
                delay = action.get("delay", 1)
                WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, xpath)))
                if action_type == "click":
                    driver.find_element(By.XPATH, xpath).click()
                elif action_type == "input":
                    input_value = action.get("value", "")
                    elem = driver.find_element(By.XPATH, xpath)
                    elem.clear()
                    elem.send_keys(input_value)
                time.sleep(delay)
        else:
            pass

    def final_crawl(self, driver):
        final_elem = driver.find_element(By.XPATH, self.config["final_crawl_xpath"])
        return final_elem.text

##############################################
# 사이트 설정
##############################################
site_configs = {
    "B.C": {
        "login_url": "https://www.accounts-bc.com/signin",
        "login_id": "juyeonglee911029@gmail.com",
        "login_pw": "12Qwaszx!@",
        "login_id_xpath": "/html/body/div[1]/ul/li[2]/div/ul/li[2]/div[1]/div/input",
        "login_pw_xpath": "/html/body/div[1]/ul/li[2]/div/ul/li[2]/div[2]/div/div/input",
        "login_button_xpath": "/html/body/div[1]/ul/li[2]/div/ul/li[3]/button",
        "otp_xpath": "/html/body/div[1]/ul/li[2]/div/ul/li[2]/div/div[1]/div/input",
        "post_login_url": "https://scoutdata.feedconstruct.com/",
        "click_xpath1": "", "click_xpath2": "", "click_xpath3": "",
        "final_crawl_xpath": "/html/body/app-root/app-app/div/div[2]/app-game-section/div/div/div[2]/div/div[1]/div/div/mat-form-field/div[1]/div[2]/div[1]/input",
        "otp_value": "",
        "site_name": "B.C"
    },
    "VECT PAY": {
        "login_url": "https://kba-europe.com/login/?redirect_to=https%3A%2F%2Fkba-europe.com",
        "login_id": "아이디에요",
        "login_pw": "비번이에요",
        "login_id_xpath": "/html/body/div[1]/div/div[3]/div[1]/div/div/div[3]/div[2]/div/div/div/div/div/div/form/div/div[1]/div/div[1]/div[1]/input",
        "login_pw_xpath": "/html/body/div[1]/div/div[3]/div[1]/div/div/div[3]/div[2]/div/div/div/div/div/div/form/div/div[1]/div/div[1]/div[2]/input",
        "login_button_xpath": "/html/body/div[1]/div/div[3]/div[1]/div/div/div[3]/div[2]/div/div/div/div/div/div/form/div/div[1]/div/div[2]/button",
        "otp_xpath": "/html/body/div[1]/div/div[3]/div[1]/div/div/div[3]/div[2]/div/div/div/div/div/div[2]/form/div/div[1]/div/div[1]/div[1]/input",
        "post_login_url": "https://www.winglobalpay.com/",
        "click_xpath1": "/html/body/div[1]/div[1]/header/button[1]",
        "click_xpath2": "/html/body/div[1]/div[2]/nav/ul/li[2]/a",
        "click_xpath3": "/html/body/div[1]/div[2]/nav/ul/li[2]/ul/li[1]/a",
        "final_crawl_xpath": "/html/body/div[1]/div/div[3]/div[2]/div/div/div/div/div/div/div[2]/ul/li[3]",
        "otp_value": "",
        "site_name": "VECT PAY"
    },
    "WING PAY": {
        "login_url": "https://nid.naver.com/nidlogin.login?mode=form&url=https://www.naver.com/",
        "login_id": "아이디입니다",
        "login_pw": "비밀번호입니다",
        "login_id_xpath": "/html/body/div[1]/div[2]/div/div[1]/form/ul/li/div/div[1]/div/div[1]/input",
        "login_pw_xpath": "/html/body/div[1]/div[2]/div/div[1]/form/ul/li/div/div[1]/div/div[2]/input",
        "login_button_xpath": "/html/body/div[1]/div[2]/div/div[1]/form/ul/li/div/div[11]/button",
        "otp_xpath": "",
        "post_login_url": "",
        "click_xpath1": "", "click_xpath2": "", "click_xpath3": "",
        "final_crawl_xpath": "/html/body/div[1]/div[1]/div[2]/div/div/div[4]/div[1]/div/div[1]/div/ul/li[1]/a/span",
        "otp_value": "",
        "site_name": "WING PAY"
    },
    "개인장 출금": {
        "login_url": "https://www.pushbullet.com/1",
        "login_id": "your_gein_id",
        "login_pw": "your_gein_pw",
        "login_id_xpath": "XPath_GEIN_LOGIN_ID",
        "login_pw_xpath": "XPath_GEIN_LOGIN_PW",
        "login_button_xpath": "XPath_GEIN_LOGIN_BTN",
        "otp_xpath": "",
        "post_login_url": "https://www.pushbullet.com/1",
        "click_xpath1": "XPath_GEIN_CLICK1",
        "click_xpath2": "XPath_GEIN_CLICK2",
        "click_xpath3": "XPath_GEIN_CLICK3",
        "final_crawl_xpath": "XPath_GEIN_FINAL",
        "otp_value": "",
        "site_name": "개인장 출금"
    },
    "개인장 잔액": {
        "login_url": "https://www.pushbullet.com/1",
        "login_id": "your_gein_id",
        "login_pw": "your_gein_pw",
        "login_id_xpath": "XPath_GEIN_LOGIN_ID",
        "login_pw_xpath": "XPath_GEIN_LOGIN_PW",
        "login_button_xpath": "XPath_GEIN_LOGIN_BTN",
        "otp_xpath": "",
        "post_login_url": "https://www.pushbullet.com/1",
        "click_xpath1": "XPath_GEIN_CLICK1",
        "click_xpath2": "XPath_GEIN_CLICK2",
        "click_xpath3": "XPath_GEIN_CLICK3",
        "final_crawl_xpath": "XPath_GEIN_FINAL",
        "otp_value": "",
        "site_name": "개인장 잔액"
    },
    "LEVEL 장": {
        "login_url": "https://www.pushbullet.com/1",
        "login_id": "your_level_id",
        "login_pw": "your_level_pw",
        "login_id_xpath": "XPath_LEVEL_LOGIN_ID",
        "login_pw_xpath": "XPath_LEVEL_LOGIN_PW",
        "login_button_xpath": "XPath_LEVEL_LOGIN_BTN",
        "otp_xpath": "",
        "post_login_url": "https://www.netflix.com/dashboard",
        "click_xpath1": "XPath_LEVEL_CLICK1",
        "click_xpath2": "XPath_LEVEL_CLICK2",
        "click_xpath3": "XPath_LEVEL_CLICK3",
        "final_crawl_xpath": "XPath_LEVEL_FINAL",
        "otp_value": "",
        "site_name": "LEVEL 장"
    }
}

##############################################
# Login 화면
##############################################
class LoginWidget(QWidget):
    login_success = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    def setup_ui(self):
        self.setMinimumSize(300,150)
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        form_group = QGroupBox("")
        form_group.setStyleSheet("background-color: #FFFFFF; border: none;")
        form_layout = QVBoxLayout()
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("아이디")
        self.username_edit.setFixedHeight(30)
        self.username_edit.setText("EXTA")
        self.username_edit.setStyleSheet("font-size: 10pt; color: #333333; background-color: #D3D3D3;")
        self.username_edit.setFixedWidth(120)
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("비밀번호")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setFixedHeight(30)
        self.password_edit.setText("papa")
        self.password_edit.setStyleSheet("font-size: 10pt; color: #333333; background-color: #D3D3D3;")
        self.password_edit.setFixedWidth(120)
        form_layout.addWidget(QLabel("ID :"))
        form_layout.addWidget(self.username_edit)
        form_layout.addWidget(QLabel("Password :"))
        form_layout.addWidget(self.password_edit)
        form_group.setLayout(form_layout)
        main_layout.addWidget(form_group, alignment=Qt.AlignCenter)
        self.login_button = AnimatedButton("로그인")
        self.login_button.clicked.connect(self.handle_login)
        self.login_button.setFixedSize(120,30)
        main_layout.addWidget(self.login_button, alignment=Qt.AlignCenter)
        self.success_label = QLabel("로그인 성공")
        self.success_label.setAlignment(Qt.AlignCenter)
        self.success_label.setStyleSheet("color: green; font-size: 12pt;")
        self.success_label.setVisible(False)
        main_layout.addWidget(self.success_label, alignment=Qt.AlignCenter)
    def handle_login(self):
        if self.username_edit.text().strip() == "EXTA" and self.password_edit.text().strip() == "papa":
            self.show_success_message()
        else:
            QMessageBox.warning(self, "오류", "아이디 또는 비밀번호가 올바르지 않습니다.")
    def show_success_message(self):
        self.success_label.setVisible(True)
        QTimer.singleShot(2000, self.fade_out_success_message)
    def fade_out_success_message(self):
        effect = QGraphicsOpacityEffect(self.success_label)
        self.success_label.setGraphicsEffect(effect)
        self.anim = QPropertyAnimation(effect, b"opacity")
        self.anim.setDuration(1000)
        self.anim.setStartValue(1)
        self.anim.setEndValue(0)
        self.anim.finished.connect(lambda: self.login_success.emit("EXTA"))
        self.anim.start()

##############################################
# 메인 인터페이스 (5행×2열 그리드 레이아웃)
##############################################
class MainInterfaceWidget(QWidget):
    def __init__(self, login_id, parent=None):
        super().__init__(parent)
        self.login_id = login_id
        self.modify_buttons = {}
        self.fetch_edits = {}
        self.otp_inputs = {}  # OTP 위젯은 config의 otp_xpath가 있을 때만 추가됨
        self.send_buttons = {}
        self.bottom_info = QLabel("")
        self.last_success_label = QLabel("")
        self.last_success_label.setStyleSheet("font-size: 15pt; color: blue; font-weight: bold;")
        self.result_msg_label = QLabel("")
        self.result_msg_label.setVisible(False)
        self.configs = site_configs
        self.setup_ui()
        self.start_timer()
        QTimer.singleShot(5000, self.start_site_automation_all)
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        title = QLabel("자동 정산 시스템")
        title.setStyleSheet("font-size: 13pt; color: #0066CC;")
        main_layout.addWidget(title)
        grid = QGridLayout()
        grid.setSpacing(5)
        # 행0: 좌측 – B.C, 우측 – VECT PAY
        grid.addWidget(QLabel("B.C"), 0, 0)
        bc_widget = QWidget()
        bc_layout = QHBoxLayout(bc_widget)
        bc_layout.setContentsMargins(0,0,0,0)
        bc_layout.setSpacing(5)
        bc_field = NumberLineEdit()
        bc_field.setReadOnly(True)
        bc_field.setPlaceholderText("자동 업데이트 / 수동 입력")
        bc_field.setAlignment(Qt.AlignCenter)
        bc_field.setStyleSheet("font-size: 11pt; color: white; background-color: black;")
        bc_layout.addWidget(bc_field)
        self.fetch_edits["B.C"] = bc_field
        bc_btn = AnimatedButton("수정")
        bc_btn.setFixedSize(60,30)
        bc_btn.clicked.connect(lambda checked, s="B.C": self.modify_auto_update(s))
        bc_layout.addWidget(bc_btn)
        self.modify_buttons["B.C"] = bc_btn
        if self.configs["B.C"].get("otp_xpath", "").strip():
            otp_bc = QLineEdit()
            otp_bc.setMaxLength(6)
            otp_bc.setPlaceholderText("OTP 입력")
            otp_bc.setAlignment(Qt.AlignCenter)
            otp_bc.setStyleSheet("font-size: 11pt; color: white; background-color: black;")
            otp_bc.setFixedSize(100,30)
            bc_layout.addWidget(otp_bc)
            self.otp_inputs["B.C"] = otp_bc
            send_bc = AnimatedButton("전송")
            send_bc.setFixedSize(60,30)
            send_bc.setStyleSheet("color: #0066CC; background-color: transparent;")
            send_bc.clicked.connect(lambda checked, s="B.C": self.send_otp(s))
            bc_layout.addWidget(send_bc)
            self.send_buttons["B.C"] = send_bc
        grid.addWidget(bc_widget, 0, 1)
        grid.addWidget(QLabel("VECT PAY"), 0, 2)
        vp_field = NumberLineEdit()
        vp_field.setReadOnly(True)
        vp_field.setPlaceholderText("자동 업데이트 / 수동 입력")
        vp_field.setAlignment(Qt.AlignCenter)
        vp_field.setStyleSheet("font-size: 11pt; color: white; background-color: black;")
        grid.addWidget(vp_field, 0, 3)
        self.fetch_edits["VECT PAY"] = vp_field
        # 행1: 좌측 – 합계, 우측 – WING PAY
        grid.addWidget(QLabel("합계"), 1, 0)
        sum_field = NumberLineEdit()
        sum_field.setReadOnly(True)
        sum_field.setText("0")
        sum_field.setAlignment(Qt.AlignCenter)
        sum_field.setStyleSheet("font-size: 11pt; color: white; background-color: black;")
        grid.addWidget(sum_field, 1, 1)
        self.sum_edit = sum_field
        grid.addWidget(QLabel("WING PAY"), 1, 2)
        wing_field = NumberLineEdit()
        wing_field.setReadOnly(True)
        wing_field.setPlaceholderText("자동 업데이트 / 수동 입력")
        wing_field.setAlignment(Qt.AlignCenter)
        wing_field.setStyleSheet("font-size: 11pt; color: white; background-color: black;")
        grid.addWidget(wing_field, 1, 3)
        self.fetch_edits["WING PAY"] = wing_field
        # 행2: 좌측 – 정산 결과, 우측 – LEVEL 장
        grid.addWidget(QLabel("정산 결과"), 2, 0)
        result_field = NumberLineEdit()
        result_field.setReadOnly(True)
        result_field.setText("0")
        result_field.setAlignment(Qt.AlignCenter)
        result_field.setStyleSheet("font-size: 11pt; color: white; background-color: black;")
        grid.addWidget(result_field, 2, 1)
        self.settlement_edit = result_field
        grid.addWidget(QLabel("LEVEL 장"), 2, 2)
        level_field = NumberLineEdit()
        level_field.setReadOnly(True)
        level_field.setPlaceholderText("자동 업데이트 / 수동 입력")
        level_field.setAlignment(Qt.AlignCenter)
        level_field.setStyleSheet("font-size: 11pt; color: white; background-color: black;")
        grid.addWidget(level_field, 2, 3)
        self.fetch_edits["LEVEL 장"] = level_field
        # 행3: 좌측 – 중복 승인, 우측 – 개인장 출금
        grid.addWidget(QLabel("중복 승인"), 3, 0)
        approval_field = NumberLineEdit()
        approval_field.setReadOnly(True)
        approval_field.setPlaceholderText("수동 입력")
        approval_field.setAlignment(Qt.AlignCenter)
        approval_field.setStyleSheet("font-size: 11pt; color: white; background-color: black;")
        grid.addWidget(approval_field, 3, 1)
        self.fetch_edits["중복 승인"] = approval_field
        grid.addWidget(QLabel("개인장 출금"), 3, 2)
        out_field = NumberLineEdit()
        out_field.setReadOnly(True)
        out_field.setPlaceholderText("자동 업데이트 / 수동 입력")
        out_field.setAlignment(Qt.AlignCenter)
        out_field.setStyleSheet("font-size: 11pt; color: white; background-color: black;")
        grid.addWidget(out_field, 3, 3)
        self.fetch_edits["개인장 출금"] = out_field
        # 행4: 좌측 – 입금 후 미신청, 우측 – 개인장 잔액
        grid.addWidget(QLabel("입금 후 미신청"), 4, 0)
        notapplied_field = NumberLineEdit()
        notapplied_field.setReadOnly(True)
        notapplied_field.setPlaceholderText("수동 입력")
        notapplied_field.setAlignment(Qt.AlignCenter)
        notapplied_field.setStyleSheet("font-size: 11pt; color: white; background-color: black;")
        grid.addWidget(notapplied_field, 4, 1)
        self.fetch_edits["입금 후 미신청"] = notapplied_field
        grid.addWidget(QLabel("개인장 잔액"), 4, 2)
        balance_field = NumberLineEdit()
        balance_field.setReadOnly(True)
        balance_field.setPlaceholderText("자동 업데이트 / 수동 입력")
        balance_field.setAlignment(Qt.AlignCenter)
        balance_field.setStyleSheet("font-size: 11pt; color: white; background-color: black;")
        grid.addWidget(balance_field, 4, 3)
        self.fetch_edits["개인장 잔액"] = balance_field
        main_layout.addLayout(grid)
        main_layout.addWidget(self.result_msg_label)
        main_layout.addWidget(self.last_success_label)
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self.bottom_info = QLabel(f"사용자: {self.login_id}    {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
        self.bottom_info.setStyleSheet("font-size: 12pt; color: #333333;")
        bottom_layout.addWidget(self.bottom_info)
        bottom_layout.addStretch()
        main_layout.addLayout(bottom_layout)
        self.setLayout(main_layout)
    def modify_auto_update(self, site):
        field = self.fetch_edits.get(site)
        btn = self.modify_buttons.get(site)
        if field is None or btn is None:
            return
        if field.isReadOnly():
            field.setReadOnly(False)
            field.selectAll()
            btn.setText("완료")
            btn.setStyleSheet("color: #00FF00;")
        else:
            field.setReadOnly(True)
            effect = QGraphicsOpacityEffect(field)
            field.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b"opacity")
            anim.setDuration(500)
            anim.setStartValue(1)
            anim.setEndValue(0.7)
            anim.start()
            field.setStyleSheet("background-color: grey; color: white;")
            btn.setText("수정")
            btn.setStyleSheet("color: #0066CC;")
            self.calculate_settlement()
    def send_otp(self, site):
        otp_val = self.otp_inputs[site].text() if self.otp_inputs.get(site) else ""
        self.configs[site]["otp_value"] = otp_val
        print(f"{site} OTP 전송: {otp_val}")
        if self.otp_inputs.get(site):
            self.otp_inputs[site].clear()
    def calculate_settlement(self):
        try:
            bc_val = float(re.sub(r"[^\d\.]", "", self.fetch_edits.get("B.C").text()))
        except:
            bc_val = 0.0
        try:
            approval = float(re.sub(r"[^\d\.]", "", self.fetch_edits.get("중복 승인").text()))
        except:
            approval = 0.0
        others_sum = 0.0
        for site in ["WING PAY", "VECT PAY", "LEVEL 장", "개인장 출금", "개인장 잔액"]:
            try:
                others_sum += float(re.sub(r"[^\d\.]", "", self.fetch_edits.get(site).text()))
            except:
                pass
        try:
            not_applied = float(re.sub(r"[^\d\.]", "", self.fetch_edits.get("입금 후 미신청").text()))
        except:
            not_applied = 0.0
        settlement = (bc_val + approval) - (others_sum - not_applied)
        if settlement == 0:
            self.settlement_edit.setText(f"{format_number(str(settlement))} (정상)")
            self.settlement_edit.setStyleSheet("font-size: 15pt; color: green; background-color: black;")
            self.result_msg_label.setText("")
            self.last_success_label.setText(f"최종 정상 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.last_success_label.setStyleSheet("font-size: 15pt; color: blue; font-weight: bold;")
        else:
            self.settlement_edit.setText(f"{format_number(str(settlement))} (비정상)")
            self.settlement_edit.setStyleSheet("font-size: 11pt; color: red; background-color: black;")
            if (bc_val + approval) > (others_sum - not_applied):
                msg = "증복입금 혹은 오승인 확인 요망."
            else:
                msg = "입금 후 미신청 또는 핑돈 확인 요망."
            if msg == "입금 후 미신청 또는 핑돈 확인 요망.":
                self.result_msg_label.setStyleSheet("font-size: 15pt; color: red; font-weight: bold;")
            else:
                self.result_msg_label.setStyleSheet("font-size: 15pt; color: red;")
            self.result_msg_label.setText(msg)
            self.result_msg_label.setVisible(True)
    def update_time(self):
        self.bottom_info.setText(f"사용자: {self.login_id}    {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
    def start_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.update_time()
    def start_site_automation_all(self):
        self.site_auto_threads = []
        for config in self.configs.values():
            thread = SiteAutomationThread(config)
            thread.automation_complete.connect(functools.partial(self.update_site_field, config["site_name"]))
            thread.otp_ready.connect(functools.partial(self.otp_ready, config["site_name"]))
            thread.otp_hide.connect(functools.partial(self.otp_hide, config["site_name"]))
            thread.start()
            self.site_auto_threads.append(thread)
    def update_site_field(self, site, value):
        field = self.fetch_edits.get(site)
        if value == "Automation Error":
            field.setText("X")
        else:
            if not value.strip():
                value = "0"
            field.setText(format_number(value))
            field.setStyleSheet("font-size: 11pt; color: red; background-color: black;")
        self.calculate_settlement()
    def otp_ready(self, site, dummy):
        if site in self.otp_inputs:
            self.otp_inputs[site].setVisible(True)
        if site in self.send_buttons:
            self.send_buttons[site].setVisible(True)
    def otp_hide(self, site, dummy):
        if site in self.otp_inputs:
            self.otp_inputs[site].setVisible(False)
        if site in self.send_buttons:
            self.send_buttons[site].setVisible(False)

##############################################
# MainWindow
##############################################
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("실시간 정산 시스템")
        self.resize(400,300)
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        self.login_widget = LoginWidget()
        self.login_widget.login_success.connect(self.on_login_success)
        self.stacked_widget.addWidget(self.login_widget)
    def on_login_success(self, login_id):
        self.main_interface = MainInterfaceWidget(login_id)
        self.stacked_widget.addWidget(self.main_interface)
        self.stacked_widget.setCurrentWidget(self.main_interface)
    def closeEvent(self, event):
        event.accept()

##############################################
# 종료 처리 함수
##############################################
def cleanup():
    print("프로그램 종료, 모든 브라우저 종료")
atexit.register(cleanup)

##############################################
# 메인 함수
##############################################
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet("""
* { font-family: 'Malgun Gothic', sans-serif; }
QWidget { background-color: #F0F0F0; color: #333333; }
QGroupBox { background-color: #FFFFFF; border: none; }
QLineEdit { background-color: black; border: none; border-radius: 5px; padding: 6px; font-size: 11pt; color: white; }
QPushButton { background-color: #E0E0E0; border: none; border-radius: 5px; padding: 8px 16px; font-size: 9pt; color: #333333; }
QPushButton:hover { background-color: #D0D0D0; }
""")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
