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
# [기능] 슈퍼 청소기 (모든 팝업 제거)
# ==========================================
def clear_all_popups(d):
    """화면을 가리는 모든 방해꾼(로그인, 키보드, 약관)을 찾아내서 닫음"""
    try:
        # 1. 크롬/구글 로그인 (대소문자/띄어쓰기 변종 모두 대응)
        # textContains를 사용하여 부분 일치도 잡아냄
        if d(textContains="Sign in to Chrome").exists or d(textContains="Welcome to Chrome").exists:
            print("   🧹 [청소] 크롬 로그인 화면 감지 -> 거절 클릭")
            if d(textContains="No thanks").exists: d(textContains="No thanks").click()
            elif d(textContains="No Thanks").exists: d(textContains="No Thanks").click()
            elif d(textContains="NO THANKS").exists: d(textContains="NO THANKS").click()
            elif d(resourceId="com.android.chrome:id/negative_button").exists: d(resourceId="com.android.chrome:id/negative_button").click()
            time.sleep(1)

        # 2. Gboard (키보드) 설정 팝업 [이미지 2번 원인]
        if d(textContains="better keyboard").exists:
            print("   🧹 [청소] 키보드 설정 팝업 감지 -> 거절 클릭")
            if d(textContains="No, thanks").exists: d(textContains="No, thanks").click()
            elif d(textContains="No thanks").exists: d(textContains="No thanks").click()
            time.sleep(1)

        # 3. 약관 동의
        if d(textContains="Accept").exists: 
            d(textContains="Accept").click()
            print("   🔨 약관 동의 클릭")
            
        # 4. 유튜브 프리미엄/기타
        if d(textContains="Skip trial").exists: d(textContains="Skip trial").click()
        if d(textContains="나중에").exists: d(textContains="나중에").click()
        if d(textContains="Use without").exists: d(textContains="Use without").click()
        
        # 5. 400 에러
        if d(text="RETRY").exists:
            print("   ⚠️ [오류] 400 에러 -> RETRY 클릭")
            d(text="RETRY").click()
            
    except Exception as e:
        print(f"   ⚠️ 팝업 처리 중 경미한 오류: {e}")

# ==========================================
# [기능] 안전한 텍스트 입력 (+키보드 팝업 감시)
# ==========================================
def safe_type_text(d, text):
    """입력 직후 키보드 팝업이 뜨는지 감시"""
    try:
        print(f"   ⌨️ '{text}' 입력 중...")
        d.shell(f"input text '{text}'")
        time.sleep(2) # 입력 후 팝업 뜰 시간 줌
        
        # ★ 입력하자마자 키보드 설정 팝업이 뜨면 바로 죽임
        clear_all_popups(d)
        
    except Exception as e:
        print(f"   ⚠️ 입력 중 에러: {e}")

# ==========================================
# [기능] IP 확인 (크롬) - 완벽한 확인용
# ==========================================
def check_ip_browser(d):
    print("🌐 IP 확인 (크롬)...")
    d.shell("am force-stop com.android.chrome")
    d.app_start("com.android.chrome", stop=True)
    time.sleep(5)
    
    # 사이트 가기 전에 청소
    clear_all_popups(d)
    
    # 사이트 이동
    d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io/json" -p com.android.chrome')
    time.sleep(8)
    
    # 사이트 뜨고 나서 또 청소 (로그인 창이 늦게 뜰 수 있음)
    clear_all_popups(d)
    
    print("📸 IP 확인 화면 캡처 중...")
    read_screen_text(d, filename="DEBUG_IP_CHECK.png")

# ==========================================
# [기능] 유튜브 실행
# ==========================================
def setup_youtube(d):
    print("   🔨 유튜브 실행 및 시크릿 모드 진입...")
    d.shell("am force-stop com.google.android.youtube")
    d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
    time.sleep(8)
    
    clear_all_popups(d)
    
    print("   🕵️ 시크릿 모드 진입 시도...")
    
    if d(description="Account").exists: d(description="Account").click()
    elif d(resourceId="com.google.android.youtube:id/mobile_user_account_image").exists:
        d(resourceId="com.google.android.youtube:id/mobile_user_account_image").click()
    else: d.click(0.92, 0.05)
    
    time.sleep(2)
    clear_all_popups(d) # 혹시 잘못 눌러서 딴데 갔으면 복구

    if d(resourceId="com.google.android.youtube:id/new_incognito_session_item").exists:
        d(resourceId="com.google.android.youtube:id/new_incognito_session_item").click()
        print("   ✅ 시크릿 모드 클릭")
    elif d(textContains="Turn on Incognito").exists:
        d(textContains="Turn on Incognito").click()
        print("   ✅ Turn on Incognito 클릭")
    elif d(textContains="시크릿 모드").exists:
        d(textContains="시크릿 모드").click()

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
        
        # 1. IP 확인 (방해꾼 제거 포함)
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
                    if d.app_current()['package'] != "com.google.android.youtube":
                        print("⚠️ 유튜브 이탈. 복귀 중...")
                        d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
                        time.sleep(4)
                        clear_all_popups(d)
                except: pass

                # 검색 버튼 클릭
                if d(resourceId="com.google.android.youtube:id/menu_item_search").exists:
                    d(resourceId="com.google.android.youtube:id/menu_item_search").click()
                elif d(description="Search").exists:
                    d(description="Search").click()
                else:
                    d.click(0.85, 0.05)
                
                time.sleep(2)
                
                # ★ 입력 및 키보드 팝업 즉시 제거
                safe_type_text(d, keyword) 
                
                # 엔터 누르기
                d.press("enter")
                time.sleep(8)
                
                # 결과 읽기 전 마지막 청소
                clear_all_popups(d)
                
                screen_text = read_screen_text(d, filename=f"{keyword}_{i}_top.png")
                
                # 그래도 가리는 게 있다면 재시도
                if any(x in screen_text for x in ["problem", "RETRY", "Sign in", "keyboard"]):
                    print("🧹 [복구] 아직도 팝업이 있음. 다시 청소 후 재촬영.")
                    clear_all_popups(d)
                    time.sleep(2)
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
                time.sleep(1)
                d.press("back")
                time.sleep(2)
                
    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    run_android_monitoring()
