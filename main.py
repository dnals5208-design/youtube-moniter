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
MAX_FAILURE_LIMIT = 30
WAIT_TIME = 2.0

# [설정] BrowserStack 인증 (GitHub Secrets에서 가져옴)
BS_USER = os.environ.get("BROWSERSTACK_USER")
BS_KEY = os.environ.get("BROWSERSTACK_KEY")
BS_URL = f"https://{BS_USER}:{BS_KEY}@hub-cloud.browserstack.com/wd/hub"

# ==========================================
# [함수] 광고주 분류
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
# [1단계] PC 모니터링 (가상 모니터 + Playwright)
# ==========================================
def run_pc_crawling():
    results = []
    print("\n🖥️ [PC] 모니터링 시작 (Playwright)...")
    
    with sync_playwright() as p:
        # 가상 모니터(Xvfb) 덕분에 headless=False 가능!
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="ko-KR",
            timezone_id="Asia/Seoul"
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
                        results.append({"디바이스": "PC", "회차": success, "키워드": keyword, "광고여부": "X", "광고주_구분": "미노출(시도초과)", "상세_광고주": "-", "광고형태": "-", "영상제목/배너카피": "-"})
                    break
                try:
                    page.goto(f"https://www.youtube.com/results?search_query={keyword}", wait_until="domcontentloaded")
                    time.sleep(WAIT_TIME)
                    
                    found_ad = None
                    ads = page.locator("ytd-promoted-sparkles-web-renderer, ytd-ad-slot-renderer, ytd-video-renderer").all()
                    for ad in ads:
                        txt = ad.inner_text()
                        if ("광고" in txt or "Ad" in txt or "Sponsored" in txt or "스폰서" in txt):
                            found_ad = ad; break
                    
                    if found_ad:
                        raw = found_ad.inner_text().split('\n')
                        title = raw[1] if len(raw) > 1 else raw[0]
                        advertiser = "알수없음"
                        for r in raw:
                            if len(r) < 40 and "http" not in r and r != title and "광고" not in r: 
                                advertiser = r; break
                        
                        biz, comp = classify_advertiser(advertiser + " " + title)
                        is_video = "조회수" in found_ad.inner_text()
                        results.append({"디바이스": "PC", "회차": success+1, "키워드": keyword, "광고여부": "O", "광고주_구분": comp, "상세_광고주": biz, "광고형태": "영상" if is_video else "배너", "영상제목/배너카피": title})
                        success += 1
                        print(f"   [PC] ⭕ {biz}")
                    else:
                        if keyword == "공무원":
                             results.append({"디바이스": "PC", "회차": success+1, "키워드": keyword, "광고여부": "X", "광고주_구분": "-", "상세_광고주": "-", "광고형태": "-", "영상제목/배너카피": "-"})
                             success += 1
                        else: fails += 1
                except: fails += 1
        browser.close()
    return results

# ==========================================
# [2단계] MO 모니터링 (BrowserStack - Real App)
# ==========================================
def run_real_app_crawling():
    if not BS_USER or not BS_KEY:
        print("⚠️ BrowserStack 계정 정보가 없습니다. (Secrets 확인 필요)")
        return []

    results = []
    print("\n📱 [MO] 리얼 디바이스 연결 시작 (Galaxy S23)...")
    
    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.platform_version = "13.0"
    options.device_name = "Samsung Galaxy S23"
    options.app_package = "com.google.android.youtube"
    options.app_activity = "com.google.android.apps.youtube.app.WatchWhileActivity"
    options.no_reset = False 
    
    bstack_options = {
        "projectName": "Youtube Monitor",
        "buildName": "Daily Check",
        "sessionName": "Incognito Real App",
        "userName": BS_USER,
        "accessKey": BS_KEY,
        "idleTimeout": 300
    }
    options.set_capability("bstack:options", bstack_options)
    
    driver = None
    try:
        driver = webdriver.Remote(BS_URL, options=options)
        wait = WebDriverWait(driver, 20)
        print("✅ 갤럭시 S23 연결 성공! 유튜브 앱 실행됨.")
        time.sleep(5)

        # ----------------------------------
        # 시크릿 모드 진입 시도
        # ----------------------------------
        print("🕵️ 시크릿 모드 진입 시도...")
        try:
            # 프로필(You/Account) 찾기
            try:
                profile = wait.until(EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "You")))
                profile.click()
            except:
                try:
                    profile = driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Account")
                    profile.click()
                except:
                    # S23 우측 하단 좌표 터치
                    driver.tap([(950, 2200)])
            
            time.sleep(3)
            
            # 시크릿 모드 켜기
            incognito = driver.find_element(AppiumBy.XPATH, "//*[contains(@text, 'Incognito') or contains(@text, '시크릿')]")
            incognito.click()
            time.sleep(3)
            
            try:
                got_it = driver.find_element(AppiumBy.XPATH, "//*[contains(@text, 'Got it') or contains(@text, '확인')]")
                got_it.click()
            except: pass
            
        except Exception as e:
            print(f"⚠️ 시크릿 모드 진입 이슈: {e}")

        # ----------------------------------
        # 검색 시작
        # ----------------------------------
        for keyword in KEYWORDS:
            print(f" >> [MO] '{keyword}' 검색 중...")
            success = 0
            fails = 0
            TARGET_MO_COUNT = 5 # 리얼기기는 느리니까 5개만 (조절가능)
            
            while success < TARGET_MO_COUNT:
                try:
                    search_icon = wait.until(EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "Search")))
                    search_icon.click()
                    time.sleep(1)
                    
                    search_box = driver.find_element(AppiumBy.ID, "com.google.android.youtube:id/search_edit_text")
                    search_box.clear()
                    search_box.send_keys(keyword)
                    driver.press_keycode(66) # Enter
                    time.sleep(4) # 로딩 대기
                    
                    # 광고 스캔
                    ad_found = False
                    elements = driver.find_elements(AppiumBy.XPATH, "//*[contains(@text, 'Ad') or contains(@text, '광고') or contains(@text, 'Sponsored')]")
                    real_ads = [el.text for el in elements if len(el.text) > 0]
                    
                    if len(real_ads) > 0:
                        advertiser = real_ads[0]
                        biz, comp = classify_advertiser(advertiser)
                        results.append({"디바이스": "Mobile(App)", "회차": success+1, "키워드": keyword, "광고여부": "O", "광고주_구분": comp, "상세_광고주": advertiser, "광고형태": "앱광고", "영상제목/배너카피": "-"})
                        print(f"   [MO] ⭕ 발견: {advertiser}")
                    else:
                        print("   [MO] ❌ 광고 없음")
                        if keyword == "공무원":
                             results.append({"디바이스": "Mobile(App)", "회차": success+1, "키워드": keyword, "광고여부": "X", "광고주_구분": "-", "상세_광고주": "-", "광고형태": "-", "영상제목/배너카피": "-"})
                        else:
                             results.append({"디바이스": "Mobile(App)", "회차": success+1, "키워드": keyword, "광고여부": "X", "광고주_구분": "미노출", "상세_광고주": "-", "광고형태": "-", "영상제목/배너카피": "-"})
                    
                    success += 1
                except: 
                    fails += 1
                    if fails > 2: break 

    except Exception as e:
        print(f"BrowserStack 연결 실패: {e}")
    finally:
        if driver: driver.quit()
        
    return results

if __name__ == "__main__":
    pc_data = run_pc_crawling()
    mo_data = run_real_app_crawling()
    
    final_data = pc_data + mo_data
    
    if final_data:
        df = pd.DataFrame(final_data)
        now_str = datetime.now().strftime('%Y-%m-%d-%H')
        filename = f"유튜브_광고_모니터링_{now_str}.xlsx"
        df.to_excel(filename, index=False)
        print(f"\n✅ 저장 완료: {filename}")