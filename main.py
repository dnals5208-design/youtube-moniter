import time
import uiautomator2 as u2
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import sys
import pytesseract
from PIL import Image

ADB_ADDR = "emulator-5554" 
KEYWORDS = ["해커스", "토익", "경찰공무원", "소방공무원", "공무원"]
REPEAT_COUNT = 10 
SCREENSHOT_DIR = "screenshots"

def get_worksheet():
    try:
        json_key = json.loads(os.environ['G_SHEET_KEY'])
        sheet_id = os.environ['G_SHEET_ID']
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json_key, scope)
        client = gspread.authorize(creds)
        sh = client.open_by_key(sheet_id)
        now = datetime.now()
        sheet_name = f"{now.year % 100}.{now.month}/{now.day}"
        header = ["날짜", "시간", "키워드", "회차", "광고여부", "비고"]
        try:
            worksheet = sh.worksheet(sheet_name)
            if not worksheet.get_all_values(): worksheet.append_row(header)
        except:
            worksheet = sh.add_worksheet(title=sheet_name, rows="1000", cols="20")
            worksheet.append_row(header)
        return worksheet
    except Exception as e:
        print(f"❌ 구글 시트 연결 실패: {e}")
        return None

def append_to_sheet(worksheet, data):
    if worksheet:
        try:
            row = [data["날짜"], data["시간"], data["키워드"], data["회차"], data["광고여부"], data["비고"]]
            worksheet.append_row(row)
            print("   📤 시트 저장 완료")
        except: pass

def read_screen_text(d, filename=None):
    try:
        temp_path = "current_screen.png"
        d.screenshot(temp_path)
        if filename:
            save_path = os.path.join(SCREENSHOT_DIR, filename)
            os.system(f"cp {temp_path} {save_path}")
        text = pytesseract.image_to_string(Image.open(temp_path), lang='kor+eng')
        return " ".join(text.split())
    except: return ""

def nuke_popups(d):
    """모든 방해 팝업 제거"""
    try:
        # 1. 크롬/구글 로그인
        if d(textContains="Accept").exists: d(textContains="Accept").click()
        if d(textContains="No thanks").exists: d(textContains="No thanks").click()
        if d(textContains="No Thanks").exists: d(textContains="No Thanks").click()
        if d(resourceId="com.android.chrome:id/negative_button").exists: d(resourceId="com.android.chrome:id/negative_button").click()
        
        # 2. 키보드 팝업
        if d(textContains="better keyboard").exists:
            d(textContains="No").click()
        
        # 3. 400 에러 (RETRY)
        if d(text="RETRY").exists:
            print("   ⚠️ [오류] 400 에러 -> RETRY 클릭")
            d(text="RETRY").click()
            time.sleep(3)

        # 4. 기타
        if d(text="Skip trial").exists: d(text="Skip trial").click()
        if d(text="나중에").exists: d(text="나중에").click()
        if d(text="Got it").exists: d(text="Got it").click()
    except: pass

# ==========================================
# [1단계] IP 확인
# ==========================================
def check_ip_browser(d):
    print("🌐 IP 확인 시작...")
    d.shell("am force-stop com.android.chrome")
    d.app_start("com.android.chrome", stop=True)
    time.sleep(5)
    
    nuke_popups(d)
    d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io/json" -p com.android.chrome')
    
    print("   ⏳ 로딩 대기 (15초)...")
    time.sleep(15)
    nuke_popups(d)
    
    print("📸 IP 확인 화면 캡처")
    read_screen_text(d, filename="DEBUG_IP_CHECK.png")

# ==========================================
# [2단계] 유튜브 준비 (스크린샷 추가)
# ==========================================
def setup_youtube(d):
    print("   🧹 유튜브 앱 데이터 초기화...")
    d.shell("pm clear com.google.android.youtube") 
    time.sleep(2)
    
    print("   🔨 유튜브 실행...")
    d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
    time.sleep(10)
    
    # ★ 요청 1: 유튜브 켜자마자 스크린샷
    print("📸 [디버그] 유튜브 시작 화면 저장")
    d.screenshot(os.path.join(SCREENSHOT_DIR, "DEBUG_1_YOUTUBE_START.png"))
    
    nuke_popups(d)
    
    print("   🕵️ 시크릿 모드 진입 시도 (우하단 -> 중앙)...")
    
    # 1. 우하단 'Library' 클릭
    d.click(0.9, 0.95) 
    time.sleep(3)

    # ★ 요청 2: Library 들어간 직후 스크린샷
    print("📸 [디버그] Library 진입 화면 저장")
    d.screenshot(os.path.join(SCREENSHOT_DIR, "DEBUG_2_LIBRARY_ENTER.png"))
    
    nuke_popups(d)
    
    # 2. 중앙 버튼 찾기
    if d(textContains="Sign in").exists:
        d(textContains="Sign in").click()
    elif d(description="Account").exists:
        d(description="Account").click()
    else:
        print("   ⚠️ 중앙 버튼 없음, 우상단 클릭")
        d.click(0.92, 0.05)
        
    time.sleep(2)
    
    # ★ 요청 3: 시크릿 메뉴 찾기 전 스크린샷
    print("📸 [디버그] 시크릿 메뉴 찾기 전 화면 저장")
    d.screenshot(os.path.join(SCREENSHOT_DIR, "DEBUG_3_INCOGNITO_MENU.png"))
    
    # 3. 시크릿 모드 클릭
    if d(textContains="Turn on Incognito").exists:
        d(textContains="Turn on Incognito").click()
        print("   ✅ 시크릿 모드 켜기 성공")
    elif d(resourceId="com.google.android.youtube:id/new_incognito_session_item").exists:
        d(resourceId="com.google.android.youtube:id/new_incognito_session_item").click()
        print("   ✅ 시크릿 모드 켜기 성공 (ID)")
    
    time.sleep(5)
    if d(text="Got it").exists: d(text="Got it").click()

# ==========================================
# [3단계] 검색
# ==========================================
def perform_search(d, keyword):
    print(f"   🔍 '{keyword}' 검색 시도...")
    
    # 돋보기
    if d(description="Search").exists: d(description="Search").click()
    elif d(resourceId="com.google.android.youtube:id/menu_item_search").exists: d(resourceId="com.google.android.youtube:id/menu_item_search").click()
    else: d.click(0.85, 0.05)
    
    time.sleep(2)
    
    # 키보드 팝업 즉시 제거
    if d(textContains="better keyboard").exists:
        d(textContains="No").click()
        time.sleep(1)
        if d(resourceId="com.google.android.youtube:id/search_edit_text").exists:
             d(resourceId="com.google.android.youtube:id/search_edit_text").click()
    
    # 입력 (set_text)
    search_box = d(resourceId="com.google.android.youtube:id/search_edit_text")
    if search_box.exists:
        search_box.set_text(keyword)
    else:
        d.shell(f"input text '{keyword}'")
    
    time.sleep(1)
    d.press("enter")
    time.sleep(1)
    d.click(0.9, 0.9) # 엔터 보조
    time.sleep(8)

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 에뮬레이터 연결...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        check_ip_browser(d)
        setup_youtube(d)

        for keyword in KEYWORDS:
            print(f"\n🔎 [{keyword}] 검색 시작")
            
            for i in range(1, REPEAT_COUNT + 1):
                sys.stdout.flush()
                print(f"   [{i}/{REPEAT_COUNT}] 진행 중...", end=" ")
                
                # 앱 이탈시 복귀
                if d.app_current()['package'] != "com.google.android.youtube":
                    d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
                    time.sleep(5)
                
                # 400 에러 체크
                nuke_popups(d) 

                perform_search(d, keyword)
                
                nuke_popups(d)
                
                screen_text = read_screen_text(d, filename=f"{keyword}_{i}_top.png")
                
                # 오류 발견
                if "problem" in screen_text or "RETRY" in screen_text:
                    print("🧹 400 에러 -> 복구 시도")
                    nuke_popups(d)
                    time.sleep(3)
                    screen_text = read_screen_text(d, filename=f"{keyword}_{i}_retry.png")

                d.swipe(500, 1500, 500, 500, 0.3) 
                time.sleep(2)
                
                is_ad = "X"
                ad_text = "-"
                if any(x in screen_text for x in ["광고", "Ad", "Sponsored"]):
                    is_ad = "O"
                    ad_text = "광고 발견"
                    if "해커스" in screen_text: ad_text = "해커스 광고"
                    print(f"🚨 발견! ({ad_text})")
                else:
                    print(f"❌ 없음 (인식: {screen_text[:15]}...)")
                
                result_data = {
                    "날짜": datetime.now().strftime('%Y-%m-%d'),
                    "시간": datetime.now().strftime('%H:%M:%S'),
                    "키워드": keyword,
                    "회차": i,
                    "광고여부": is_ad, 
                    "비고": f"{ad_text}"
                }
                append_to_sheet(ws, result_data)
                
                d.press("back")
                time.sleep(2)
                
    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    run_android_monitoring()
