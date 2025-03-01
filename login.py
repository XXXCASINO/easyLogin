import tkinter as tk
from tkinter import ttk
import threading, time, datetime, io
from PIL import ImageGrab

# Selenium 관련 모듈
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
# WebDriver Manager
from webdriver_manager.chrome import ChromeDriverManager
# explicit wait
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def format_money(value):
    try:
        num = int(str(value).replace(',', ''))
        return format(num, ',')
    except Exception:
        return value

class SettlementCrawlerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("실시간 정산 크롤링 프로그램")
        self.geometry("980x577")
        self.resizable(False, False)
        self.configure(bg="#2E2E2E")
        self.style = ModernStyle(self)
        
        self.custom_font = ("Segoe UI", 12)
        self.entry_bg = "#424242"
        self.manual_fg = "#FFFFFF"
        self.crawling_fg = "red"
        self.btn_width = 8
        
        self.crawling_control = {}
        self.start_buttons = {}
        
        # ─── 입금 정산 섹션 ───
        self.deposit_section = tk.LabelFrame(self, text="입금 정산", font=("Segoe UI", 14),
                                             fg="red", bg="#2E2E2E", bd=2, relief="groove")
        self.deposit_section.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        self.deposit_left_frame = ttk.Frame(self.deposit_section)
        self.deposit_left_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")
        self.deposit_right_frame = ttk.Frame(self.deposit_section)
        self.deposit_right_frame.grid(row=0, column=1, padx=10, pady=5, sticky="nsew")
        self.deposit_left_frame.grid_columnconfigure(0, minsize=120)
        self.deposit_right_frame.grid_columnconfigure(0, minsize=120)
        
        deposit_left_names = ["B.C", "합계", "정산 결과", "입금 후 미신청", "증복 승인", "전일 금액"]
        self.left_fields = {}
        self.left_entries = {}
        self.deposit_editable = {}
        for r, name in enumerate(deposit_left_names):
            lbl = ttk.Label(self.deposit_left_frame, text=name)
            lbl.grid(row=r, column=0, padx=5, pady=5, sticky="w")
            var = tk.StringVar()
            ent = tk.Entry(self.deposit_left_frame, textvariable=var, font=self.custom_font,
                           justify="right", relief="flat", bg=self.entry_bg, fg=self.manual_fg)
            ent.grid(row=r, column=1, padx=5, pady=5, sticky="e")
            self.left_fields[name] = var
            self.left_entries[name] = ent
            if name in ["합계", "정산 결과"]:
                ent.bind("<KeyPress>", lambda event, n=name: "break")
            else:
                if name == "B.C":
                    self.deposit_editable[name] = False
                    start_btn = ttk.Button(self.deposit_left_frame, text="시작", width=self.btn_width,
                                             style="Start.TButton",
                                             command=lambda n=name, s="left": self.toggle_crawling(n, s))
                    start_btn.grid(row=r, column=3, padx=5)
                    self.start_buttons[(name, "left")] = start_btn
                    mod_btn = ttk.Button(self.deposit_left_frame, text="수정", width=self.btn_width,
                                           command=lambda n=name: self.toggle_edit_deposit(n, "left"))
                    mod_btn.grid(row=r, column=2, padx=5)
                    ent.bind("<KeyPress>", lambda event, n=name: self.on_key_press_deposit(event, n))
                    ent.bind("<KeyRelease>", lambda event, n=name: self.on_numeric_key_release_deposit(event, n))
                elif name == "전일 금액":
                    self.deposit_editable[name] = False
                    mod_btn = ttk.Button(self.deposit_left_frame, text="수정", width=self.btn_width,
                                           command=lambda n=name: self.toggle_edit_deposit(n, "left"))
                    mod_btn.grid(row=r, column=2, padx=5)
                    ent.bind("<KeyPress>", lambda event, n=name: self.on_key_press_deposit(event, n))
                    ent.bind("<KeyRelease>", lambda event, n=name: self.on_numeric_key_release_deposit(event, n))
                else:
                    ent.bind("<KeyRelease>", lambda event, n=name: self.on_numeric_key_release_deposit(event, n))
        
        self.right_fields = {}
        self.right_entries = {}
        self.deposit_right_editable = {}
        for r, name in enumerate(["VECT PAY", "WING PAY", "GOLD PAY 잔액", "GOLD PAY 출금", "LVL 장"]):
            lbl = ttk.Label(self.deposit_right_frame, text=name)
            lbl.grid(row=r, column=0, padx=5, pady=5, sticky="w")
            var = tk.StringVar()
            ent = tk.Entry(self.deposit_right_frame, textvariable=var, font=self.custom_font,
                           justify="right", relief="flat", bg=self.entry_bg, fg=self.manual_fg)
            ent.grid(row=r, column=1, padx=5, pady=5, sticky="e")
            self.right_fields[name] = var
            self.right_entries[name] = ent
            self.deposit_right_editable[name] = False
            mod_btn = ttk.Button(self.deposit_right_frame, text="수정", width=self.btn_width,
                                  command=lambda n=name: self.toggle_edit_deposit_right(n))
            mod_btn.grid(row=r, column=2, padx=5)
            start_btn = ttk.Button(self.deposit_right_frame, text="시작", width=self.btn_width,
                                     style="Start.TButton",
                                     command=lambda n=name, s="right": self.toggle_crawling(n, s))
            start_btn.grid(row=r, column=3, padx=5)
            self.start_buttons[(name, "right")] = start_btn
            ent.bind("<KeyPress>", lambda event, n=name: self.on_key_press_deposit_right(event, n))
            ent.bind("<KeyRelease>", lambda event, n=name: self.on_numeric_key_release_deposit_right(event, n))
        
        self.deposit_settlement_label = ttk.Label(self.deposit_section, text="", font=("Segoe UI", 11), foreground="lime")
        self.deposit_settlement_label.grid(row=1, column=0, columnspan=2, pady=5)
        
        self.withdraw_section = tk.LabelFrame(self, text="출금 정산", font=("Segoe UI", 14),
                                              fg="red", bg="#2E2E2E", bd=2, relief="groove")
        self.withdraw_section.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self.withdraw_left_frame = ttk.Frame(self.withdraw_section)
        self.withdraw_left_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")
        self.withdraw_right_frame = ttk.Frame(self.withdraw_section)
        self.withdraw_right_frame.grid(row=0, column=1, padx=10, pady=5, sticky="nsew")
        self.withdraw_left_frame.grid_columnconfigure(0, minsize=120)
        self.withdraw_right_frame.grid_columnconfigure(0, minsize=120)
        
        withdraw_left_names = ["B.C 출금", "출금 합계", "정산 결과"]
        self.withdraw_left_fields = {}
        self.withdraw_left_entries = {}
        self.withdraw_left_editable = {}
        for r, name in enumerate(withdraw_left_names):
            lbl = ttk.Label(self.withdraw_left_frame, text=name)
            lbl.grid(row=r, column=0, padx=5, pady=5, sticky="w")
            var = tk.StringVar()
            ent = tk.Entry(self.withdraw_left_frame, textvariable=var, font=self.custom_font,
                           justify="right", relief="flat", bg=self.entry_bg, fg=self.manual_fg)
            ent.grid(row=r, column=1, padx=5, pady=5, sticky="e")
            self.withdraw_left_fields[name] = var
            self.withdraw_left_entries[name] = ent
            if name in ["출금 합계", "정산 결과"]:
                ent.bind("<KeyPress>", lambda event, n=name: "break")
            else:
                self.withdraw_left_editable[name] = False
                mod_btn = ttk.Button(self.withdraw_left_frame, text="수정", width=self.btn_width,
                                     command=lambda n=name: self.toggle_edit_withdraw_left(n))
                mod_btn.grid(row=r, column=2, padx=5)
                start_btn = ttk.Button(self.withdraw_left_frame, text="시작", width=self.btn_width,
                                       style="Start.TButton",
                                       command=lambda n=name, s="withdraw_left": self.toggle_crawling(n, s))
                start_btn.grid(row=r, column=3, padx=5)
                self.start_buttons[(name, "withdraw_left")] = start_btn
                ent.bind("<KeyPress>", lambda event, n=name: self.on_key_press_withdraw_left(event, n))
                ent.bind("<KeyRelease>", lambda event, n=name: self.on_numeric_key_release_withdraw_left(event, n))
        
        withdraw_right_names = ["환정장 출금", "VECT PAY 출금", "뒷장", "일일 한도", "잔여 한도"]
        self.withdraw_right_fields = {}
        self.withdraw_right_entries = {}
        self.withdraw_editable = {}
        for r, name in enumerate(withdraw_right_names):
            lbl = ttk.Label(self.withdraw_right_frame, text=name)
            lbl.grid(row=r, column=0, padx=5, pady=5, sticky="w")
            var = tk.StringVar()
            ent = tk.Entry(self.withdraw_right_frame, textvariable=var, font=self.custom_font,
                           justify="right", relief="flat", bg=self.entry_bg, fg=self.manual_fg, width=15)
            ent.grid(row=r, column=1, padx=5, pady=5, sticky="e")
            self.withdraw_right_fields[name] = var
            self.withdraw_right_entries[name] = ent
            if name == "VECT PAY 출금":
                self.withdraw_editable[name] = False
                mod_btn = ttk.Button(self.withdraw_right_frame, text="수정", width=self.btn_width,
                                     command=lambda n=name: self.toggle_edit_withdraw(n))
                mod_btn.grid(row=r, column=2, padx=5)
                start_btn = ttk.Button(self.withdraw_right_frame, text="시작", width=self.btn_width,
                                         style="Start.TButton",
                                         command=lambda n=name, s="right": self.toggle_crawling(n, s))
                start_btn.grid(row=r, column=3, padx=5)
                self.start_buttons[(name, "right")] = start_btn
                ent.bind("<KeyPress>", lambda event, n=name: self.on_key_press_withdrawal(event, n))
                ent.bind("<KeyRelease>", lambda event, n=name: self.on_numeric_key_release_withdrawal(event, n))
            elif name in ("일일 한도", "잔여 한도"):
                ent.bind("<KeyPress>", lambda event, n=name: self.on_key_press_withdrawal(event, n))
                ent.bind("<KeyRelease>", lambda event, n=name: self.on_numeric_key_release_withdrawal_auto(event, n))
            else:
                self.withdraw_editable[name] = False
                mod_btn = ttk.Button(self.withdraw_right_frame, text="수정", width=self.btn_width,
                                     command=lambda n=name: self.toggle_edit_withdraw(n))
                mod_btn.grid(row=r, column=2, padx=5)
                ent.bind("<KeyPress>", lambda event, n=name: self.on_key_press_withdrawal(event, n))
                ent.bind("<KeyRelease>", lambda event, n=name: self.on_numeric_key_release_withdrawal(event, n))
        
        self.withdraw_settlement_label = ttk.Label(self.withdraw_section, text="", font=("Segoe UI", 11), foreground="lime")
        self.withdraw_settlement_label.grid(row=1, column=0, columnspan=2, pady=5)
        
        self.screenshot_button = ttk.Button(self, text="스크린샷", width=self.btn_width, command=self.copy_screenshot)
        self.copy_text_button = ttk.Button(self, text="정보 취출", width=self.btn_width, command=self.copy_text_info)
        self.screenshot_button.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)
        self.copy_text_button.place(relx=1.0, rely=1.0, anchor="se", x=-110, y=-10)
        
        self.scoutdata_label = ttk.Label(self, text="", style="TLabel")
        self.scoutdata_label.place(relx=0.5, rely=0.95, anchor="center")
        
        self.status_label = ttk.Label(self, text="", style="TLabel")
        self.status_label.grid(row=2, column=0, columnspan=2, pady=5)
        self.update_clock()
    
    # OTP 폴링 함수 (별도 쓰레드에서 4초마다 체크)
    def otp_polling(self, driver, stop_event, xpath="OTP_ELEMENT_XPATH"):
        while not stop_event.is_set():
            try:
                element = driver.find_element(By.XPATH, xpath)
                if element and element.is_displayed():
                    self.after(0, self.show_otp_input, driver, element)
                    time.sleep(4)  # OTP 입력창이 뜨면 4초 대기 후 다시 체크
                else:
                    time.sleep(4)
            except Exception:
                time.sleep(4)
    
    def start_otp_polling(self, driver, stop_event, xpath="OTP_ELEMENT_XPATH"):
        threading.Thread(target=self.otp_polling, args=(driver, stop_event, xpath), daemon=True).start()
    
    def toggle_crawling(self, field_name, side):
        key = (field_name, side)
        if key in self.crawling_control:
            self.crawling_control[key]["stop_event"].set()
            self.start_buttons[key].config(text="시작", style="Start.TButton")
        else:
            stop_event = threading.Event()
            t = threading.Thread(target=self.run_field_crawling, args=(field_name, side, stop_event), daemon=True)
            self.crawling_control[key] = {"thread": t, "stop_event": stop_event}
            t.start()
            self.start_buttons[key].config(text="정지", style="Stop.TButton")
    
    def run_field_crawling(self, field_name, side, stop_event):
        # 19초 주기: refresh 후 18초 대기, 값 추출 후 1초 대기
        if field_name == "B.C" and side == "left":
            options = Options()
            options.headless = False
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            try:
                driver.get("https://www.accounts-bc.com/signin")
                if stop_event.is_set(): return
                time.sleep(4)
                driver.find_element(By.XPATH, "/html/body/div[1]/ul/li[2]/div/ul/li[2]/div[1]/div/input").send_keys("juyeonglee911029@gmail.com")
                if stop_event.is_set(): return
                time.sleep(4)
                driver.find_element(By.XPATH, "/html/body/div[1]/ul/li[2]/div/ul/li[2]/div[2]/div/div/input").send_keys("12Qwaszx!@")
                if stop_event.is_set(): return
                time.sleep(4)
                driver.find_element(By.XPATH, "/html/body/div[1]/ul/li[2]/div/ul/li[3]/button").click()
                if stop_event.is_set(): return
                time.sleep(4)
                # OTP 폴링 시작 (B.C)
                self.start_otp_polling(driver, stop_event, "OTP_ELEMENT_XPATH")
                if stop_event.is_set(): return
                time.sleep(4)
                driver.get("https://scoutdata.feedconstruct.com/")
                if stop_event.is_set(): return
                time.sleep(4)
                while not stop_event.is_set():
                    driver.refresh()
                    time.sleep(18)
                    try:
                        element = WebDriverWait(driver, 30).until(
                            EC.presence_of_element_located((By.XPATH, "/html/body/app-root/app-app/div/div[1]/app-header/div/div/div/div/div[3]/div[1]/span[2]"))
                        )
                        formatted = element.text.strip()
                        self.after(0, self.update_field, formatted, field_name, side)
                    except Exception as e:
                        print("B.C 입금 크롤링 오류:", e)
                        self.after(0, self.update_field, "0", field_name, side)
                    time.sleep(1)
            except Exception as e:
                print("B.C 입금 시퀀스 오류:", e)
            finally:
                driver.quit()
        elif field_name == "VECT PAY" and side == "right":
            options = Options()
            options.headless = False
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            try:
                driver.get("https://nid.naver.com/nidlogin.login")
                if stop_event.is_set(): return
                time.sleep(4)
                driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div/div[1]/form/ul/li/div/div[1]/div/div[1]/input").send_keys("YOUR_VECT_ID")
                if stop_event.is_set(): return
                time.sleep(4)
                driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div/div[1]/form/ul/li/div/div[1]/div/div[2]/input").send_keys("YOUR_VECT_PASSWORD")
                if stop_event.is_set(): return
                time.sleep(4)
                driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div/div[1]/form/ul/li/div/div[11]/button").click()
                if stop_event.is_set(): return
                time.sleep(4)
                self.start_otp_polling(driver, stop_event, "OTP_ELEMENT_XPATH")
                if stop_event.is_set(): return
                driver.get("https://m.stock.naver.com/worldstock/home/USA/marketValue/NASDAQ")
                if stop_event.is_set(): return
                time.sleep(4)
                while not stop_event.is_set():
                    driver.refresh()
                    time.sleep(18)
                    try:
                        element = WebDriverWait(driver, 30).until(
                            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[1]/div[2]/div/div[3]/div[1]/ul/li[1]/a/div[1]/span[1]"))
                        )
                        processed_text = element.text[1:]
                        try:
                            number = int(processed_text.replace(',', ''))
                            formatted = format_money(number)
                        except:
                            formatted = processed_text
                        self.after(0, self.update_field, formatted, field_name, side)
                    except Exception as e:
                        print("VECT PAY 크롤링 오류:", e)
                        self.after(0, self.update_field, "0", field_name, side)
                    time.sleep(1)
            except Exception as e:
                print("VECT PAY 시퀀스 오류:", e)
            finally:
                driver.quit()
        elif field_name == "WING PAY" and side == "right":
            options = Options()
            options.headless = False
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            try:
                driver.get("https://m.stock.naver.com/domestic/capitalization/total")
                if stop_event.is_set(): return
                time.sleep(18)
                try:
                    element = WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[1]/div[2]/div/div[3]/div[1]/ul/li[1]/a/div[1]/span[1]"))
                    )
                    formatted = format_money(element.text.strip())
                    self.after(0, self.update_field, formatted, field_name, side)
                except Exception as e:
                    print("WING PAY 크롤링 오류:", e)
                    self.after(0, self.update_field, "0", field_name, side)
                while not stop_event.is_set():
                    driver.refresh()
                    time.sleep(18)
                    try:
                        element = WebDriverWait(driver, 30).until(
                            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[1]/div[2]/div/div/div[6]/div[1]/table/tbody/tr[1]/td[5]"))
                        )
                        formatted = format_money(element.text.strip())
                        self.after(0, self.update_field, formatted, field_name, side)
                    except Exception as e:
                        print("WING PAY 크롤링 오류:", e)
                        self.after(0, self.update_field, "0", field_name, side)
                    time.sleep(1)
            except Exception as e:
                print("WING PAY 시퀀스 오류:", e)
            finally:
                driver.quit()
        elif field_name == "B.C 출금" and side == "withdraw_left":
            options = Options()
            options.headless = False
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            try:
                driver.get("https://www.accounts-bc.com/signin")
                if stop_event.is_set(): return
                time.sleep(4)
                driver.find_element(By.XPATH, "/html/body/div[1]/ul/li[2]/div/ul/li[2]/div[1]/div/input").send_keys("juyeonglee911029@gmail.com")
                if stop_event.is_set(): return
                time.sleep(4)
                driver.find_element(By.XPATH, "/html/body/div[1]/ul/li[2]/div/ul/li[2]/div[2]/div/div/input").send_keys("12Qwaszx!@")
                if stop_event.is_set(): return
                time.sleep(4)
                driver.find_element(By.XPATH, "/html/body/div[1]/ul/li[2]/div/ul/li[3]/button").click()
                if stop_event.is_set(): return
                time.sleep(4)
                try:
                    otp_elem = driver.find_element(By.XPATH, "/html/body/div[1]/ul/li[2]/div/ul/li[2]/div/div[1]/div/input")
                    self.start_otp_polling(driver, stop_event, "OTP_ELEMENT_XPATH")
                except Exception:
                    self.show_login_success_message("계좌 로그인 성공")
                if stop_event.is_set(): return
                time.sleep(4)
                driver.get("https://scoutdata.feedconstruct.com/")
                if stop_event.is_set(): return
                time.sleep(4)
                while not stop_event.is_set():
                    driver.refresh()
                    time.sleep(18)
                    try:
                        element = WebDriverWait(driver, 30).until(
                            EC.presence_of_element_located((By.XPATH, "/html/body/app-root/app-auth/div/div[2]/app-login/div/div[1]/div"))
                        )
                        updated_value = element.text
                        sub_text = updated_value[3:-1]
                        try:
                            number = int(sub_text.replace(',', ''))
                            formatted = format_money(number)
                        except:
                            formatted = sub_text
                        self.after(0, self.update_field, formatted, field_name, side)
                    except Exception as e:
                        print("B.C 출금 크롤링 오류:", e)
                        self.after(0, self.update_field, "0", field_name, side)
                    time.sleep(1)
            except Exception as e:
                print("B.C 출금 시퀀스 오류:", e)
            finally:
                driver.quit()
        elif field_name == "VECT PAY 출금" and side == "right":
            options = Options()
            options.headless = False
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            try:
                driver.get("https://nid.naver.com/nidlogin.login")
                if stop_event.is_set(): return
                time.sleep(4)
                driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div/div[1]/form/ul/li/div/div[1]/div/div[1]/input").send_keys("YOUR_VECT_ID")
                if stop_event.is_set(): return
                time.sleep(4)
                driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div/div[1]/form/ul/li/div/div[1]/div/div[2]/input").send_keys("YOUR_VECT_PASSWORD")
                if stop_event.is_set(): return
                time.sleep(4)
                driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div/div[1]/form/ul/li/div/div[11]/button").click()
                if stop_event.is_set(): return
                time.sleep(4)
                try:
                    otp_elem = driver.find_element(By.XPATH, "OTP_ELEMENT_XPATH")
                    self.start_otp_polling(driver, stop_event, "OTP_ELEMENT_XPATH")
                except Exception:
                    self.show_login_success_message("로그인 성공")
                if stop_event.is_set(): return
                driver.get("https://m.stock.naver.com/worldstock/home/USA/marketValue/NASDAQ")
                if stop_event.is_set(): return
                time.sleep(4)
                while not stop_event.is_set():
                    driver.refresh()
                    time.sleep(18)
                    try:
                        element = WebDriverWait(driver, 30).until(
                            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[1]/div[2]/div/div/div[3]/div[1]/div[1]/strong"))
                        )
                        processed_text = element.text[:-1]
                        try:
                            number = int(processed_text.replace(',', ''))
                            formatted = format_money(number)
                        except:
                            formatted = processed_text
                        self.after(0, self.update_field, formatted, field_name, side)
                    except Exception as e:
                        print("VECT PAY 출금 크롤링 오류:", e)
                        self.after(0, self.update_field, "0", field_name, side)
                    time.sleep(1)
            except Exception as e:
                print("VECT PAY 출금 시퀀스 오류:", e)
            finally:
                driver.quit()
        else:
            dummy_values = {
                "WING PAY": 250000,
                "GOLD PAY 잔액": 400000,
                "GOLD PAY 출금": 350000,
                "LVL 장": 500000,
                "B.C 출금": 1800000,
                "환정장 출금": 0,
                "VECT PAY 출금": 300000,
                "뒷장": 0,
                "일일 한도": 0,
                "잔여 한도": 0
            }
            while not stop_event.is_set():
                value = dummy_values.get(field_name, 0)
                fmt_val = format_money(value)
                self.after(0, self.update_field, fmt_val, field_name, side)
                time.sleep(4)
        key = (field_name, side)
        self.after(0, lambda: self.start_buttons[key].config(text="시작", style="Start.TButton"))
        if key in self.crawling_control:
            self.crawling_control.pop(key)
    
    def update_field(self, value, field_name, side):
        if side == "left":
            if field_name in self.left_fields:
                self.left_fields[field_name].set(value)
                self.left_entries[field_name].configure(fg=self.crawling_fg)
            elif field_name in self.withdraw_left_fields:
                self.withdraw_left_fields[field_name].set(value)
                self.withdraw_left_entries[field_name].configure(fg=self.crawling_fg)
        elif side == "right":
            if field_name in self.right_fields:
                self.right_fields[field_name].set(value)
                self.right_entries[field_name].configure(fg=self.crawling_fg)
            elif field_name in self.withdraw_right_fields:
                self.withdraw_right_fields[field_name].set(value)
                self.withdraw_right_entries[field_name].configure(fg=self.crawling_fg)
        self.recalc_deposit()
        self.recalc_withdrawal()
    
    def show_otp_input(self, driver, otp_elem):
        def send_otp():
            otp_value = otp_entry.get()
            try:
                otp_elem.clear()
                otp_elem.send_keys(otp_value + Keys.ENTER)
            except Exception as e:
                print("OTP 전송 오류:", e)
            top.destroy()
        top = tk.Toplevel(self)
        top.title("OTP 입력")
        tk.Label(top, text="OTP 입력:", font=self.custom_font).pack(padx=10, pady=5)
        otp_entry = tk.Entry(top, font=self.custom_font)
        otp_entry.pack(padx=10, pady=5)
        send_btn = ttk.Button(top, text="전송", command=send_otp, width=self.btn_width)
        send_btn.pack(padx=10, pady=5)
        top.grab_set()
    
    def show_login_success_message(self, msg):
        success_lbl = ttk.Label(self, text=msg, foreground="lime")
        success_lbl.place(relx=0, rely=1.0, anchor="sw", x=10, y=-10)
        self.after(2000, lambda: success_lbl.destroy())
    
    def recalc_deposit(self):
        try:
            wing_pay = int(self.right_fields["WING PAY"].get().replace(',', ''))
        except:
            wing_pay = 0
        try:
            vect_pay = int(self.right_fields["VECT PAY"].get().replace(',', ''))
        except:
            vect_pay = 0
        try:
            gold_pay_balance = int(self.right_fields["GOLD PAY 잔액"].get().replace(',', ''))
        except:
            gold_pay_balance = 0
        try:
            gold_pay_withdraw = int(self.right_fields["GOLD PAY 출금"].get().replace(',', ''))
        except:
            gold_pay_withdraw = 0
        try:
            lvl = int(self.right_fields["LVL 장"].get().replace(',', ''))
        except:
            lvl = 0
        try:
            not_applied = int(self.left_fields["입금 후 미신청"].get().replace(',', ''))
        except:
            not_applied = 0
        total = (wing_pay + vect_pay + gold_pay_withdraw + gold_pay_balance + lvl) - not_applied
        self.left_fields["합계"].set(format_money(total))
        try:
            bc_val = int(self.left_fields["B.C"].get().replace(',', ''))
        except:
            bc_val = 0
        settlement_result = bc_val - total
        diff = abs(settlement_result)
        if settlement_result == 0:
            res_text = f"정상 (차이: {format_money(diff)})"
            color = "lime"
            self.deposit_settlement_label.config(text=f"최종 정산일치 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            if settlement_result < 0:
                res_text = f"입금 후 미신청 (부족: {format_money(diff)})"
            else:
                res_text = f"증복 승인 (초과: {format_money(diff)})"
            color = "red"
        self.left_fields["정산 결과"].set(res_text)
        self.left_entries["정산 결과"].configure(fg=color)
    
    def toggle_edit_deposit(self, field_name, side):
        self.deposit_editable[field_name] = True
        ent = self.left_entries[field_name]
        ent.configure(fg=self.manual_fg)
        ent.focus_set()
        ent.selection_range(0, tk.END)
        self.recalc_deposit()
    
    def on_key_press_deposit(self, event, field_name):
        if (field_name, "left") in self.crawling_control and not self.deposit_editable.get(field_name, False):
            return "break"
    
    def on_numeric_key_release_deposit(self, event, field_name):
        if (field_name, "left") in self.crawling_control and not self.deposit_editable.get(field_name, False):
            return "break"
        widget = event.widget
        current = widget.get()
        digits = ''.join(filter(str.isdigit, current))
        if not digits:
            widget.delete(0, tk.END)
            self.recalc_deposit()
            return
        try:
            num = int(digits)
        except:
            num = 0
        fmt = format_money(num)
        if current != fmt:
            widget.delete(0, tk.END)
            widget.insert(0, fmt)
        widget.configure(fg=self.manual_fg)
        self.recalc_deposit()
    
    def toggle_edit_deposit_right(self, field_name):
        self.deposit_right_editable[field_name] = True
        ent = self.right_entries[field_name]
        ent.configure(fg=self.manual_fg)
        ent.focus_set()
        ent.selection_range(0, tk.END)
        self.recalc_deposit()
    
    def on_key_press_deposit_right(self, event, field_name):
        if (field_name, "right") in self.crawling_control and not self.deposit_right_editable.get(field_name, False):
            return "break"
    
    def on_numeric_key_release_deposit_right(self, event, field_name):
        if (field_name, "right") in self.crawling_control and not self.deposit_right_editable.get(field_name, False):
            return "break"
        widget = event.widget
        current = widget.get()
        digits = ''.join(filter(str.isdigit, current))
        if not digits:
            widget.delete(0, tk.END)
            self.recalc_deposit()
            return
        try:
            num = int(digits)
        except:
            num = 0
        fmt = format_money(num)
        if current != fmt:
            widget.delete(0, tk.END)
            widget.insert(0, fmt)
        widget.configure(fg=self.manual_fg)
        self.recalc_deposit()
    
    def toggle_edit_withdraw_left(self, field_name):
        self.withdraw_left_editable[field_name] = True
        ent = self.withdraw_left_entries[field_name]
        ent.configure(fg=self.manual_fg)
        ent.focus_set()
        ent.selection_range(0, tk.END)
        self.recalc_withdrawal()
    
    def on_key_press_withdraw_left(self, event, field_name):
        if (field_name, "withdraw_left") in self.crawling_control:
            return "break"
    
    def on_numeric_key_release_withdraw_left(self, event, field_name):
        if (field_name, "withdraw_left") in self.crawling_control:
            return "break"
        widget = event.widget
        current = widget.get()
        digits = ''.join(filter(str.isdigit, current))
        if not digits:
            widget.delete(0, tk.END)
            self.recalc_withdrawal()
            return
        try:
            num = int(digits)
        except:
            num = 0
        fmt = format_money(num)
        if current != fmt:
            widget.delete(0, tk.END)
            widget.insert(0, fmt)
        widget.configure(fg=self.manual_fg)
        self.recalc_withdrawal()
    
    def toggle_edit_withdraw(self, field_name):
        self.withdraw_editable[field_name] = True
        ent = self.withdraw_right_entries[field_name]
        ent.configure(fg=self.manual_fg)
        ent.focus_set()
        ent.selection_range(0, tk.END)
        self.recalc_withdrawal()
    
    def on_key_press_withdrawal(self, event, field_name):
        if (field_name, "right") in self.crawling_control and not self.withdraw_editable.get(field_name, False):
            return "break"
    
    def on_numeric_key_release_withdrawal(self, event, field_name):
        if (field_name, "right") in self.crawling_control and not self.withdraw_editable.get(field_name, False):
            return "break"
        widget = event.widget
        current = widget.get()
        digits = ''.join(filter(str.isdigit, current))
        if not digits:
            widget.delete(0, tk.END)
            self.recalc_withdrawal()
            return
        try:
            num = int(digits)
        except:
            num = 0
        fmt = format_money(num)
        if current != fmt:
            widget.delete(0, tk.END)
            widget.insert(0, fmt)
        widget.configure(fg=self.manual_fg)
        self.recalc_withdrawal()
    
    def on_numeric_key_release_withdrawal_auto(self, event, field_name):
        if (field_name, "right") in self.crawling_control and not self.withdraw_editable.get(field_name, False):
            return "break"
        widget = event.widget
        current = widget.get()
        digits = ''.join(filter(str.isdigit, current))
        if not digits:
            widget.delete(0, tk.END)
            self.auto_update_hw()
            self.recalc_withdrawal()
            return
        try:
            num = int(digits)
        except:
            num = 0
        fmt = format_money(num)
        if current != fmt:
            widget.delete(0, tk.END)
            widget.insert(0, fmt)
        widget.configure(fg=self.manual_fg)
        self.auto_update_hw()
        self.recalc_withdrawal()
    
    def auto_update_hw(self):
        daily = self.withdraw_right_fields["일일 한도"].get()
        remaining = self.withdraw_right_fields["잔여 한도"].get()
        if daily and remaining:
            try:
                d = int(daily.replace(',', ''))
                r = int(remaining.replace(',', ''))
                computed = d - r
                self.withdraw_right_fields["환정장 출금"].set(format_money(computed))
                self.withdraw_right_entries["환정장 출금"].configure(fg=self.crawling_fg)
            except:
                pass
        self.recalc_withdrawal()
    
    def recalc_withdrawal(self):
        try:
            bc_withdraw = int(self.withdraw_left_fields["B.C 출금"].get().replace(',', ''))
        except:
            bc_withdraw = 0
        try:
            hw = int(self.withdraw_right_fields["환정장 출금"].get().replace(',', ''))
        except:
            hw = 0
        try:
            vect = int(self.withdraw_right_fields["VECT PAY 출금"].get().replace(',', ''))
        except:
            vect = 0
        try:
            back = int(self.withdraw_right_fields["뒷장"].get().replace(',', ''))
        except:
            back = 0
        total = hw + vect + back
        self.withdraw_left_fields["출금 합계"].set(format_money(total))
        result = bc_withdraw - total
        if result == 0 or result == back:
            res_text = f"정상 (차이: {format_money(abs(result))})"
            color = "lime"
            self.withdraw_settlement_label.config(text=f"최종 정산일치 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        elif result > 0:
            res_text = f"증복 출금 (초과: {format_money(result)})"
            color = "red"
        else:
            res_text = f"오출금 (부족: {format_money(abs(result))})"
            color = "red"
        self.withdraw_left_fields["정산 결과"].set(res_text)
        self.withdraw_left_entries["정산 결과"].configure(fg=color)
    
    def update_clock(self):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.status_label.configure(text=now)
        self.after(1000, self.update_clock)
    
    def copy_screenshot(self):
        try:
            x = self.winfo_rootx()
            y = self.winfo_rooty()
            w = self.winfo_width()
            h = self.winfo_height()
            bbox = (x, y, x + w, y + h)
            img = ImageGrab.grab(bbox)
            output = io.BytesIO()
            img.convert("RGB").save(output, "BMP")
            data = output.getvalue()[14:]
            output.close()
            import win32clipboard, win32con
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_DIB, data)
            win32clipboard.CloseClipboard()
            print("스크린샷이 클립보드에 복사되었습니다.")
        except Exception as e:
            print("스크린샷 복사 오류:", e)
    
    def copy_text_info(self):
        info_lines = []
        info_lines.append("=== 입금 정산 ===")
        for key in ["B.C", "합계", "정산 결과", "입금 후 미신청", "증복 승인", "전일 금액"]:
            value = self.left_fields.get(key, tk.StringVar()).get()
            info_lines.append(f"{key}: {value}")
        for key in ["VECT PAY", "WING PAY", "GOLD PAY 잔액", "GOLD PAY 출금", "LVL 장"]:
            value = self.right_fields.get(key, tk.StringVar()).get()
            info_lines.append(f"{key}: {value}")
        info_lines.append("")
        info_lines.append("=== 출금 정산 ===")
        for key in ["B.C 출금", "출금 합계", "정산 결과"]:
            value = self.withdraw_left_fields.get(key, tk.StringVar()).get()
            info_lines.append(f"{key}: {value}")
        for key in ["환정장 출금", "VECT PAY 출금", "뒷장", "일일 한도", "잔여 한도"]:
            value = self.withdraw_right_fields.get(key, tk.StringVar()).get()
            info_lines.append(f"{key}: {value}")
        settlement_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        info_lines.append("")
        info_lines.append("정산 시간: " + settlement_time)
        info_text = "\n".join(info_lines)
        self.clipboard_clear()
        self.clipboard_append(info_text)
        print("정보가 텍스트로 클립보드에 복사되었습니다.")

class ModernStyle(ttk.Style):
    def __init__(self, root):
        super().__init__(root)
        self.theme_use('clam')
        self.configure("TFrame", background="#2E2E2E")
        self.configure("TLabel", background="#2E2E2E", foreground="#E0E0E0", font=("Segoe UI", 12))
        self.configure("TButton", background="#424242", foreground="#E0E0E0", font=("Segoe UI", 10), borderwidth=0)
        self.map("TButton", background=[("active", "#616161")])
        self.configure("Start.TButton", foreground="red", font=("Segoe UI", 10))
        self.map("Start.TButton", foreground=[("active", "red")])
        self.configure("Stop.TButton", foreground="lime", font=("Segoe UI", 10))
        self.map("Stop.TButton", foreground=[("active", "lime")])

if __name__ == "__main__":
    app = SettlementCrawlerApp()
    app.mainloop()
