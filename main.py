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
# [기능] 슈퍼 청소기 (팝업/오류 제거)
# ==========================================
def clear_all_popups(d):
    """오류나 팝업이 있으면 True 반환, 없으면 False"""
    try:
        # OCR 없이 빠르게 체크 가능한 UI 요소들 먼저 처리
        if d(text="RETRY").exists:
            print("   ⚠️ [오류] 400 에러 발견 -> RETRY 클릭")
            d(text="RETRY").click()
            time.sleep(3)
            return True
            
        # 키보드 팝업 (가장 중요)
        if d(textContains="better keyboard").exists:
            print("   🔨 키보드 팝업(Gboard) 제거")
            if d(textContains="No, thanks").exists: d(textContains="No, thanks").click()
            elif d(textContains="No thanks").exists: d(textContains="No thanks").click()
            return True

        # 로그인/환영
        if d(textContains="Sign in").exists or d(textContains="Welcome").exists:
             print("   🔨 로그인/환영 화면 제거")
             if d(textContains="No thanks").exists: d(textContains="No thanks").click()
             elif d(resourceId="com.android.chrome:id/negative_button").exists: d(resourceId="com.android.chrome:id/negative_button").click()
             return True

        if d(text="Skip trial").exists: 
            d(text="Skip trial").click()
            return True
            
    except: pass
    return False

# ==========================================
# [기능] 유튜브 상태 확인
# ==========================================
def ensure_youtube_ready(d):
    """400 에러나 팝업이 사라질 때까지 대기"""
    print("   🏥 유튜브 상태 점검 중...")
    for _ in range(3):
        had_error = clear_all_popups(d)
        if not had_error: return
        time.sleep(2)

# ==========================================
# [기능] 집요한 입력 (입력 검증 + 재시도)
# ==========================================
def perform_search_action(d, text):
    """검색창에 글자가 들어갔는지 확인하고, 안 들어갔으면 팝업 끄고 다시 입력"""
    try:
        # 1. 먼저 검색창을 확실하게 클릭 (ID 기반)
        print("   👆 검색바 클릭 (포커스 잡기)")
        if d(resourceId="com.google.android.youtube:id/search_edit_text").exists:
            d(resourceId="com.google.android.youtube:id/search_edit_text").click()
        else:
            # 검색바가 없으면 돋보기 버튼을 안 누른 상태일 수 있음. 그냥 진행
            pass
            
        time.sleep(1)
        
        # 2. 키보드 팝업이 떴을 수 있으니 선제 공격
        clear_all_popups(d)
        
        # 3. 입력 시도 (최대 3회)
        for attempt in range(3):
            print(f"   ⌨️ '{text}' 입력 시도 ({attempt+1}/3)...")
            d.shell(f"input text '{text}'")
            time.sleep(2)
            
            # 팝업이 또 가렸는지 체크
            clear_all_popups(d)
            
            # ★ [핵심] 글자가 진짜 들어갔는지 확인
            current_text = ""
            if d(resourceId="com.google.android.youtube:id/search_edit_text").exists:
                current_text = d(resourceId="com.google.android.youtube:id/search_edit_text").get_text()
            
            if current_text == text:
                print("   ✅ 입력 확인됨. 엔터 실행.")
                break
            else:
                print(f"   ⚠️ 입력 실패 (현재값: '{current_text}'). 팝업 제거 후 재시도...")
                clear_all_popups(d)
                # 검색바 다시 클릭해서 포커스 가져오기
                if d(resourceId="com.google.android.youtube:id/search_edit_text").exists:
                    d(resourceId="com.google.android.youtube:id/search_edit_text").click()
                time.sleep(1)

        # 4. 엔터 실행 (키보드 엔터 + 물리 버튼 클릭)
        print("   👆 엔터키 입력")
        d.press("enter")
        time.sleep(1)
        
        # 혹시 엔터 안 먹혔을까봐 파란 버튼 위치 강제 클릭
        print("   👆 엔터(좌표) 보조 클릭")
        d.click(0.9, 0.9) 
        time.sleep(8)
        
    except Exception as e:
        print(f"   ⚠️ 입력 중 에러: {e}")

# ==========================================
# [기능] IP 확인 (크롬) - 로딩 대기 강화
# ==========================================
def check_ip_browser(d):
    print("🌐 IP 확인 (크롬)...")
    d.shell("am force-stop com.android.chrome")
    d.app_start("com.android.chrome", stop=True)
    time.sleep(5)
    clear_all_popups(d)
    
    d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io/json" -p com.android.chrome')
    
    print("   ⏳ 사이트 로딩 대기 (15초)...")
    time.sleep(15)
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
    time.sleep(10)
    
    ensure_youtube_ready(d)
    
    print("   🕵️ 시크릿 모드 진입 시도...")
    if d(description="Account").exists: d(description="Account").click()
    elif d(resourceId="com.google.android.youtube:id/mobile_user_account_image").exists:
        d(resourceId="com.google.android.youtube:id/mobile_user_account_image").click()
    else: d.click(0.92, 0.05)
    
    time.sleep(2)
    clear_all_popups(d)

    if d(resourceId="com.google.android.youtube:id/new_incognito_session_item").exists:
        d(resourceId="com.google.android.youtube:id/new_incognito_session_item").click()
        print("   ✅ 시크릿 모드 클릭")
    elif d(textContains="Turn on Incognito").exists:
        d(textContains="Turn on Incognito").click()
    elif d(textContains="시크릿 모드").exists:
        d(textContains="시크릿 모드").click()

    time.sleep(5)
    if d(text="Got it").exists: d(text="Got it").click()

# ==========================================
# [메인] 실행 로직
# ==========================================
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
                
                # 1. 앱 이탈 체크
                if d.app_current()['package'] != "com.google.android.youtube":
                    print("⚠️ 유튜브 이탈. 복귀 중...")
                    d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
                    time.sleep(5)

                # 2. 상태 점검
                ensure_youtube_ready(d)

                # 3. 검색 버튼 클릭
                if d(resourceId="com.google.android.youtube:id/menu_item_search").exists:
                    d(resourceId="com.google.android.youtube:id/menu_item_search").click()
                elif d(description="Search").exists:
                    d(description="Search").click()
                else:
                    d.click(0.85, 0.05)
                
                time.sleep(2)
                
                # 4. ★ 입력 (검증 포함)
                perform_search_action(d, keyword)
                
                # 5. 결과 확인
                clear_all_popups(d)
                screen_text = read_screen_text(d, filename=f"{keyword}_{i}_top.png")
                
                # 오류 화면이면 재시도
                if any(x in screen_text for x in ["problem", "RETRY", "400"]):
                    print("🧹 [복구] 검색 실패(오류). 재시도.")
                    ensure_youtube_ready(d)
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
