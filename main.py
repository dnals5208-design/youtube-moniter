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

# ==========================================
# [설정]
# ==========================================
ADB_ADDR = "emulator-5554" 
KEYWORDS = ["해커스", "토익", "경찰공무원", "소방공무원", "공무원"]
REPEAT_COUNT = 10 
SCREENSHOT_DIR = "screenshots"

# ==========================================
# [기능] 구글 시트 연결
# ==========================================
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
            if not worksheet.get_all_values():
                worksheet.append_row(header)
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

# ==========================================
# [기능] 화면 텍스트 읽기 (OCR)
# ==========================================
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

# ==========================================
# [기능] 팝업/오류 처리기 (청소부)
# ==========================================
def handle_popups(d):
    """각종 방해꾼(로그인/오류/설정/약관) 처리"""
    try:
        screen_text = read_screen_text(d)
        
        # 1. 서버 오류 (Problem with server [400]) -> 시간 동기화 문제일 때 뜸
        if "problem" in screen_text or "400" in screen_text or "RETRY" in screen_text:
            print("   ⚠️ [오류] 서버 접속 에러(400) 감지. RETRY 클릭!")
            if d(text="RETRY").exists: d(text="RETRY").click()
            else: d.click(0.5, 0.5) # 화면 중앙 클릭
            time.sleep(3)
            
        # 2. 엉뚱한 '설정(Settings)' 화면
        if "Settings" in screen_text and "General" in screen_text:
            print("   ⚠️ [길잃음] 설정 화면 감지. 뒤로가기.")
            d.press("back")
            time.sleep(2)

        # 3. 로그인/약관/프리미엄 권유
        if d(text="Accept & continue").exists: 
            d(text="Accept & continue").click()
            print("   🔨 약관 동의 처리")
        if d(text="No thanks").exists: 
            d(text="No thanks").click()
        if d(text="Skip trial").exists: 
            d(text="Skip trial").click()
        if d(text="나중에").exists: 
            d(text="나중에").click()
        if d(text="Use without an account").exists:
            d(text="Use without an account").click()
    except: pass

# ==========================================
# [기능] 안전한 텍스트 입력 (튕김 방지)
# ==========================================
def safe_type_text(d, text):
    """키보드 앱 충돌 방지를 위해 ADB Shell로 직접 입력"""
    try:
        d.shell(f"input text '{text}'")
    except Exception as e:
        print(f"   ⚠️ 입력 중 에러: {e}")

# ==========================================
# [기능] IP 확인 (크롬)
# ==========================================
def check_ip_browser(d):
    print("🌐 IP 확인 (크롬)...")
    d.shell("am force-stop com.android.chrome")
    d.app_start("com.android.chrome", stop=True)
    time.sleep(6)
    
    handle_popups(d)
    
    # IP 사이트 접속
    d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io/json" -p com.android.chrome')
    time.sleep(8)
    
    handle_popups(d)
    
    print("📸 IP 확인 화면 캡처 중...")
    read_screen_text(d, filename="DEBUG_IP_CHECK.png")

# ==========================================
# [기능] 유튜브 실행 및 시크릿 모드
# ==========================================
def setup_youtube(d):
    print("   🔨 유튜브 실행 및 시크릿 모드 진입...")
    d.shell("am force-stop com.google.android.youtube")
    # 메인 액티비티 강제 실행
    d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
    time.sleep(10)
    
    handle_popups(d)
    
    print("   🕵️ 시크릿 모드 진입 시도...")
    
    # 1. 프로필 아이콘 클릭
    if d(description="Account").exists: d(description="Account").click()
    elif d(resourceId="com.google.android.youtube:id/mobile_user_account_image").exists:
        d(resourceId="com.google.android.youtube:id/mobile_user_account_image").click()
    else: d.click(0.92, 0.05) # 우상단 좌표
    
    time.sleep(2)
    handle_popups(d)

    # 2. 메뉴 클릭
    if d(resourceId="com.google.android.youtube:id/new_incognito_session_item").exists:
        d(resourceId="com.google.android.youtube:id/new_incognito_session_item").click()
        print("   ✅ 시크릿 모드 클릭")
    elif d(text="Turn on Incognito").exists:
        d(text="Turn on Incognito").click()
        print("   ✅ Turn on Incognito 클릭")
    elif d(text="시크릿 모드 사용").exists:
        d(text="시크릿 모드 사용").click()
    else:
        print("   ⚠️ 시크릿 버튼 못 찾음 (이미 진입했거나 UI 다름)")

    time.sleep(5)
    if d(text="Got it").exists: d(text="Got it").click()
    if d(text="확인").exists: d(text="확인").click()

# ==========================================
# [메인] 실행 로직
# ==========================================
def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 에뮬레이터 연결...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        # 1. IP 확인
        check_ip_browser(d)
        
        # 2. 유튜브 준비
        setup_youtube(d)

        for keyword in KEYWORDS:
            print(f"\n🔎 [{keyword}] 검색 시작")
            
            for i in range(1, REPEAT_COUNT + 1):
                sys.stdout.flush()
                print(f"   [{i}/{REPEAT_COUNT}] 진행 중...", end=" ")
                
                # 앱 이탈 체크
                try:
                    current_app = d.app_current()
                    if current_app['package'] != "com.google.android.youtube":
                        print("⚠️ 유튜브 이탈 감지. 복귀 중...")
                        d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
                        time.sleep(4)
                        handle_popups(d)
                except: pass

                # 검색 버튼 클릭
                if d(resourceId="com.google.android.youtube:id/menu_item_search").exists:
                    d(resourceId="com.google.android.youtube:id/menu_item_search").click()
                elif d(description="Search").exists:
                    d(description="Search").click()
                else:
                    print("❌ 검색 버튼 없음 -> 좌표 클릭 시도")
                    d.click(0.85, 0.05)
                
                time.sleep(2)
                
                # 안전한 입력
                safe_type_text(d, keyword)
                time.sleep(1)
                d.press("enter")
                time.sleep(8)
                
                # 화면 인식
                screen_text = read_screen_text(d, filename=f"{keyword}_{i}_top.png")
                
                # 오류/팝업 발견 시 처리
                if any(x in screen_text for x in ["problem", "RETRY", "Sign in", "Google", "400"]):
                    print("🧹 [복구] 오류/팝업 발견. 처리 후 스크린샷 재촬영.")
                    handle_popups(d)
                    time.sleep(3)
                    screen_text = read_screen_text(d, filename=f"{keyword}_{i}_retry.png")

                d.swipe(500, 1500, 500, 500, 0.3) 
                time.sleep(2)
                
                # 광고 판별
                is_ad = "X"
                ad_text = "-"
                if any(x in screen_text for x in ["광고", "Ad", "Sponsored"]):
                    is_ad = "O"
                    ad_text = "광고 발견"
                    if "해커스" in screen_text: ad_text = "해커스 광고"
                    print(f"🚨 발견! ({ad_text})")
                else:
                    print(f"❌ 없음 (인식: {screen_text[:15]}...)")
                
                # 시트 저장
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
                time.sleep(1)
                d.press("back")
                time.sleep(2)
                
    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    run_android_monitoring()
