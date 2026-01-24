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
TARGET_MO_SUCCESS_COUNT = 5 # 모바일은 속도 관계상 5개 (조절 가능)
MAX_FAILURE_LIMIT = 30
WAIT_TIME = 2.0

# GitHub Secrets에서 가져온 BrowserStack 키
BS_USER = os.environ.get("BROWSERSTACK_USER")
BS_KEY = os.environ.get("BROWSERSTACK_KEY")
BS_URL = f"https://{BS_USER}:{BS_KEY}@hub-cloud.browserstack.com/wd/hub"

# ==========================================
# [함수] 광고주 분류 (이미지 2번 포맷)
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
    print("\n🖥️ [PC] 모니터링 시작 (한국 서울 위치 주입)...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, # 가상모니터 덕분에 False 가능
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        # ★ 한국 위치/언어 강제 설정
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
                        results.append({"디바이스": "PC", "회차": success, "키워드": keyword, "광고여부": "X", "광고주_구분": "미노출", "상세_광고주": "-", "광고형태": "-", "영상제목/배너카피": "-"})
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
# [2단계] MO 모니터링 (BrowserStack - 한국 리얼폰)
# ==========================================
def run_real_app_crawling():
    if not BS_USER or not BS_KEY:
        print("⚠️ BrowserStack 계정 정보 없음. (MO 건너뜀)")
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
    
    # ★ 한국 IP 설정 (geoLocation: KR)
    bstack_options = {
        "projectName": "Youtube Monitor",
        "buildName": "Daily Check",
        "sessionName": "Korea Incognito Test",
        "userName": BS_USER,
        "accessKey": BS_KEY,
        "geoLocation": "KR", 
        "idleTimeout": 300
    }
    options.set_capability("bstack:options", bstack_options)
    
    driver = None
    try:
        driver = webdriver.Remote(BS_URL, options=options)
        wait = WebDriverWait(driver, 25)
        print("✅ 갤럭시 S23(한국) 연결 성공!")
        time.sleep(5)

        # ----------------------------------
        # [1회 실행] 시크릿 모드 진입
        # ----------------------------------
        print("🕵️ 시크릿 모드 진입 시도...")
        try:
            # 프로필(You/Account) 찾기
            try:
                driver.find_element(AppiumBy.ACCESSIBILITY_ID, "You").click()
            except:
                try:
                    driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Account").click()
                except:
                    driver.tap([(980, 2200)]) # 우측 하단 좌표 터치
            
            time.sleep(2)
            
            # '시크릿 모드 사용' 클릭
            try:
                driver.find_element(AppiumBy.XPATH, "//*[contains(@text, 'Incognito') or contains(@text, '시크릿')]").click()
            except:
                print("   (이미 시크릿 모드이거나 버튼 못 찾음)")
            
            time.sleep(3)
            # 팝업 닫기
            try: driver.find_element(AppiumBy.XPATH, "//*[contains(@text, 'Got it') or contains(@text, '확인')]").click()
            except: pass
            
        except Exception as e:
            print(f"⚠️ 시크릿 모드 진입 이슈 (계속 진행): {e}")

        # ----------------------------------
        # [검색 루프] 시크릿 유지한 채 검색어만 변경
        # ----------------------------------
        for keyword in KEYWORDS:
            print(f" >> [MO] '{keyword}' 검색...")
            success = 0
            fails = 0
            
            while success < TARGET_MO_SUCCESS_COUNT:
                try:
                    # 1. 돋보기(검색) 아이콘 클릭
                    try:
                        search_btn = wait.until(EC.presence_of_element_located((AppiumBy.ACCESSIBILITY_ID, "Search")))
                        search_btn.click()
                    except:
                        # 돋보기 안보이면 검색바 X버튼(Clear) 누르기
                        try:
                            driver.find_element(AppiumBy.ID, "com.google.android.youtube:id/search_clear_button").click()
                        except:
                            driver.tap([(980, 130)]) # 상단 돋보기 좌표 강제 터치
                    
                    time.sleep(1)
                    
                    # 2. 검색어 입력
                    search_box = driver.find_element(AppiumBy.ID, "com.google.android.youtube:id/search_edit_text")
                    search_box.clear() # 기존 검색어 삭제
                    search_box.send_keys(keyword)
                    driver.press_keycode(66) # Enter 키 입력
                    
                    time.sleep(3) # 검색 결과 로딩
                    
                    # 3. 광고 찾기 (Ad, 광고, Sponsored)
                    elements = driver.find_elements(AppiumBy.XPATH, "//*[contains(@text, 'Ad') or contains(@text, '광고') or contains(@text, 'Sponsored')]")
                    
                    found_valid_ad = False
                    for el in elements:
                        ad_text = el.text
                        # 너무 짧거나 의미 없는 텍스트 제외
                        if len(ad_text) > 1 and "설치" not in ad_text and "건너뛰기" not in ad_text:
                            biz, comp = classify_advertiser(ad_text)
                            results.append({"디바이스": "Mobile(App)", "회차": success+1, "키워드": keyword, "광고여부": "O", "광고주_구분": comp, "상세_광고주": ad_text, "광고형태": "앱광고", "영상제목/배너카피": "-"})
                            print(f"   [MO] ⭕ 발견: {ad_text}")
                            found_valid_ad = True
                            success += 1
                            break # 하나 찾으면 다음 회차로
                    
                    if not found_valid_ad:
                        print("   [MO] ❌ 광고 없음")
                        if keyword == "공무원":
                             results.append({"디바이스": "Mobile(App)", "회차": success+1, "키워드": keyword, "광고여부": "X", "광고주_구분": "-", "상세_광고주": "-", "광고형태": "-", "영상제목/배너카피": "-"})
                             success += 1
                        else:
                             fails += 1
                             if fails > 3: break # 3연속 실패 시 다음 키워드
                
                except Exception as e:
                    print(f"   [MO] 에러: {e}")
                    fails += 1
                    if fails > 3: break

    except Exception as e:
        print(f"BrowserStack 연결 실패: {e}")
    finally:
        if driver: driver.quit()
        
    return results

# ==========================================
# [메인 실행]
# ==========================================
if __name__ == "__main__":
    pc_data = run_pc_crawling()
    
    # PC 끝나고 3초 뒤 MO 실행
    time.sleep(3)
    
    mo_data = run_real_app_crawling()
    
    # 데이터 합치기
    final_data = pc_data + mo_data
    
    if final_data:
        df = pd.DataFrame(final_data)
        # 이미지 2번과 똑같은 컬럼 순서로 정렬
        df = df[["디바이스", "회차", "키워드", "광고여부", "광고주_구분", "상세_광고주", "광고형태", "영상제목/배너카피"]]
        
        now_str = datetime.now().strftime('%Y-%m-%d-%H')
        filename = f"유튜브_광고_모니터링_{now_str}.xlsx"
        df.to_excel(filename, index=False)
        print(f"\n✅ 최종 저장 완료: {filename}")
    else:
        print("\n❌ 데이터 수집 실패")