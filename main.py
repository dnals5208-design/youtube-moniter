import time
import pandas as pd
import os
from datetime import datetime
from playwright.sync_api import sync_playwright
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# [설정] 키워드 리스트
# ==========================================
KEYWORDS = [
    "해커스", "토익", "경찰공무원", 
    "소방공무원", "공무원", "텝스", 
    "토익스피킹", "공인중개사", "토스"
]

TARGET_SUCCESS_COUNT = 10 
# MO는 리얼 기기라 느리므로 키워드당 3~5개만 수집해도 충분함
TARGET_MO_SUCCESS_COUNT = 5
MAX_FAILURE_LIMIT = 30
WAIT_TIME = 2.0

# GitHub Secrets에서 가져옴
BS_USER = os.environ.get("BROWSERSTACK_USER")
BS_KEY = os.environ.get("BROWSERSTACK_KEY")
BS_URL = f"https://{BS_USER}:{BS_KEY}@hub-cloud.browserstack.com/wd/hub"

# ==========================================
# [함수] 광고주 분류 (이미지 2번처럼 깔끔하게)
# ==========================================
def classify_advertiser(text):
    text = text.replace(" ", "")
    if "해커스" not in text: return "타사", text
    if "공무원" in text: return "해커스공무원", "해커스"
    if "경찰" in text: return "해커스경찰", "해커스"
    if "소방" in text: return "해커스소방", "해커스"
    if "자격증" in text or "기사" in text: return "해커스자격증", "해커스"
    if "공인중개사" in text or "주택관리사" in text: return "해커스공인중개사", "해커스"
    if "금융" in text: return "해커스금융", "해커스"
    if "잡" in text or "취업" in text or "면접" in text: return "해커스잡", "해커스"
    if "편입" in text: return "해커스편입", "해커스"
    if "어학" in text or "토익" in text or "텝스" in text or "토스" in text or "오픽" in text: return "해커스어학", "해커스"
    return "해커스(기타)", "해커스"

# ==========================================
# [1단계] PC 모니터링 (한국 위치 강제 주입)
# ==========================================
def run_pc_crawling():
    results = []
    print("\n🖥️ [PC] 모니터링 시작 (한국 위치 주입)...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        # ★ [핵심] 한국 서울 좌표와 언어 설정을 강제로 박아넣음
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            geolocation={"latitude": 37.5665, "longitude": 126.9780}, # 서울 시청 좌표
            permissions=["geolocation"]
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        page = context.new_page()
        
        for keyword in KEYWORDS:
            print(f" >> [PC] '{keyword}' 검색 중...")
            success = 0
            fails = 0
            while success < TARGET_SUCCESS_COUNT:
                if fails >= MAX_FAILURE_LIMIT:
                    remaining = TARGET_SUCCESS_COUNT - success
                    for _ in range(remaining):
                        success += 1
                        results.append({"디바이스": "PC", "회차": success, "키워드": keyword, "광고여부": "X", "광고주_구분": "-", "상세_광고주": "-", "광고형태": "-", "제목/배너카피": "-"})
                    break
                try:
                    page.goto(f"https://www.youtube.com/results?search_query={keyword}", wait_until="domcontentloaded")
                    time.sleep(WAIT_TIME)
                    
                    found_ad = None
                    ads = page.locator("ytd-promoted-sparkles-web-renderer, ytd-ad-slot-renderer, ytd-video-renderer").all()
                    for ad in ads:
                        txt = ad.inner_text()
                        if ("광고" in txt or "Ad" in txt or "Sponsored" in txt or "스폰서" in txt) and len(txt) > 5:
                            found_ad = ad; break
                    
                    if found_ad:
                        raw = found_ad.inner_text().split('\n')
                        title = raw[1] if len(raw) > 1 else raw[0]
                        advertiser = "알수없음"
                        for r in raw:
                            if len(r) < 40 and "http" not in r and r != title and "광고" not in r and "조회수" not in r: 
                                advertiser = r; break
                        
                        biz, comp = classify_advertiser(advertiser + " " + title)
                        is_video = "조회수" in found_ad.inner_text()
                        
                        # 외국 광고 필터링 (선택사항: 한글 없으면 제외하려면 로직 추가 가능)
                        results.append({"디바이스": "PC", "회차": success+1, "키워드": keyword, "광고여부": "O", "광고주_구분": comp, "상세_광고주": biz, "광고형태": "영상" if is_video else "배너", "제목/배너카피": title})
                        success += 1
                        print(f"   [PC] ⭕ {biz} / {title[:15]}...")
                    else:
                        if keyword == "공무원":
                             results.append({"디바이스": "PC", "회차": success+1, "키워드": keyword, "광고여부": "X", "광고주_구분": "-", "상세_광고주": "-", "광고형태": "-", "제목/배너카피": "-"})
                             success += 1
                        else: fails += 1
                except: fails += 1
        browser.close()
    return results

# ==========================================
# [2단계] MO 모니터링 (BrowserStack - 진짜 한국 앱 환경)
# ==========================================
def run_real_app_crawling():
    if not BS_USER or not BS_KEY:
        print("⚠️ BrowserStack 계정 정보 없음.")
        return []

    results = []
    print("\n📱 [MO] 리얼 디바이스(한국IP) 연결 시작...")
    
    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.platform_version = "13.0"
    options.device_name = "Samsung Galaxy S23"
    options.app_package = "com.google.android.youtube"
    options.app_activity = "com.google.android.apps.youtube.app.WatchWhileActivity"
    options.no_reset = False 
    
    # ★ [핵심] 한국 IP로 접속하도록 설정 (geoLocation)
    bstack_options = {
        "projectName": "Youtube Monitor",
        "buildName": "Daily Check",
        "sessionName": "Korea Incognito Test",
        "userName": BS_USER,
        "accessKey": BS_KEY,
        "geoLocation": "KR", # ★★★ 이게 있어야 한국 광고가 나옵니다
        "idleTimeout": 300
    }
    options.set_capability("bstack:options", bstack_options)
    
    driver = None
    try:
        driver = webdriver.Remote(BS_URL, options=options)
        wait = WebDriverWait(driver, 20)
        print("✅ 갤럭시 S23(한국) 연결 성공!")
        time.sleep(5)

        # ----------------------------------
        # [1회 실행] 시크릿 모드 진입
        # ----------------------------------
        print("🕵️ 시크릿 모드 진입 중...")
        try:
            # You(보관함) -> 시크릿 모드 켜기
            try:
                driver.find_element(AppiumBy.ACCESSIBILITY_ID, "You").click()
            except:
                try:
                    driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Account").click()
                except:
                    driver.tap([(980, 2200)]) # 좌표 클릭
            
            time.sleep(2)
            
            # '시크릿 모드 사용' 텍스트 클릭
            try:
                driver.find_element(AppiumBy.XPATH, "//*[contains(@text, 'Incognito') or contains(@text, '시크릿')]").click()
            except:
                print("   (이미 시크릿 모드거나 버튼 못찾음)")
            
            time.sleep(3)
            # 팝업 닫기
            try: driver.find_element(AppiumBy.XPATH, "//*[contains(@text, 'Got it') or contains(@text, '확인')]").click()
            except: pass
            
        except Exception as e:
            print(f"⚠️ 시크릿 모드 진입 이슈 (계속 진행): {e}")

        # ----------------------------------
        # [무한 루프] 검색어만 바꿔가며 계속 검색
        # ----------------------------------
        for keyword in KEYWORDS:
            print(f" >> [MO] '{keyword}' 검색...")
            success = 0
            fails = 0