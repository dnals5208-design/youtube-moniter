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
# [기능] OCR (화면 읽기)
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
# [기능] 팝업 제거 (단순화)
# ==========================================
def clear_popups(d):
    """방해되는 팝업들 제거"""
    try:
        # 키보드 설정 팝업 (이게 제일 문제)
        if d(textContains="better keyboard").exists:
            print("   🔨 키보드 팝업 제거")
            if d(textContains="No, thanks").exists: d(textContains="No, thanks").click()
            elif d(textContains="No thanks").exists: d(textContains="No thanks").click()
            time.sleep(1)

        # 크롬/유튜브 로그인
        if d(textContains="Sign in").exists or d(textContains="Welcome").exists:
            if d(textContains="No thanks").exists: d(textContains="No thanks").click()
            elif d(resourceId="com.android.chrome:id/negative_button").exists: d(resourceId="com.android.chrome:id/negative_button").click()

        # 400 에러
        if d(text="RETRY").exists:
            print("   ⚠️ 400 에러 -> RETRY 클릭")
            d(text="RETRY").click()
            time.sleep(2)
            
        # 기타
        if d(text="Skip trial").exists: d(text="Skip trial").click()
        if d(text="나중에").exists: d(text="나중에").click()
    except: pass

# ==========================================
# [기능] IP 확인 (로딩 대기 추가)
# ==========================================
def check_ip_browser(d):
    print("🌐 IP 확인 (크롬)...")
    d.shell("am force-stop com.android.chrome")
    d.app_start("com.android.chrome", stop=True)
    time.sleep(5)
    clear_popups(d)
    
    d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io/json" -p com.android.chrome')
    
    # ★ [수정] 선생님 요청: 로딩 덜 된 상태 방지 (15초 대기)
    print("   ⏳ 사이트 로딩 대기 (15초)...")
    time.sleep(15)
    
    clear_popups(d) # 로딩 후 뜨는 로그인 창 제거
    
    print("📸 IP 확인 화면 캡처 중...")
    read_screen_text(d, filename="DEBUG_IP_CHECK.png")

# ==========================================
# [기능] 유튜브 실행 (앱 터치 방식 복원)
# ==========================================
def setup_youtube(d):
    print("   🔨 유튜브 실행 및 시크릿 모드 진입...")
    d.shell("am force-stop com.google.android.youtube")
    # 메인 화면으로 강제 시작
    d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
    time.sleep(10)
    
    clear_popups(d)
    
    print("   🕵️ 시크릿 모드 진입 시도...")
    
    # 프로필 아이콘
    if d(description="Account").exists: d(description="Account").click()
    elif d(resourceId="com.google.android.youtube:id/mobile_user_account_image").exists:
        d(resourceId="com.google.android.youtube:id/mobile_user_account_image").click()
    else: d.click(0.92, 0.05) # 우상단
    
    time.sleep(2)
    clear_popups(d) # 혹시 잘못 눌렀으면 복구

    # 메뉴 선택
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
        
        # 1. IP 확인 (대기 시간 늘림)
        check_ip_browser(d)
        
        # 2. 유튜브 실행
        setup_youtube(d)

        for keyword in KEYWORDS:
            print(f"\n🔎 [{keyword}] 검색 시작")
            
            for i in range(1, REPEAT_COUNT + 1):
                sys.stdout.flush()
                print(f"   [{i}/{REPEAT_COUNT}] 진행 중...", end=" ")
                
                # 앱 이탈 체크
                if d.app_current()['package'] != "com.google.android.youtube":
                    print("⚠️ 유튜브 복귀...")
                    d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
                    time.sleep(5)

                # 400 에러 체크 (검색 전)
                clear_popups(d)

                # 1. 돋보기 버튼 클릭
                if d(resourceId="com.google.android.youtube:id/menu_item_search").exists:
                    d(resourceId="com.google.android.youtube:id/menu_item_search").click()
                elif d(description="Search").exists:
                    d(description="Search").click()
                else:
                    d.click(0.85, 0.05)
                
                time.sleep(2)

                # ★ [핵심 수정] 키보드 팝업이 뜨면 닫고 -> 다시 검색창 누르고 -> 입력
                if d(textContains="better keyboard").exists:
                    print("   🔨 키보드 팝업 제거")
                    d(textContains="No, thanks").click()
                    time.sleep(1)
                    # 팝업 닫히면 포커스 잃을 수 있으므로 다시 검색창 클릭
                    if d(resourceId="com.google.android.youtube:id/search_edit_text").exists:
                        d(resourceId="com.google.android.youtube:id/search_edit_text").click()
                    time.sleep(1)
                
                # 2. 입력 (선생님이 쓰던 방식 복원)
                d.clear_text()
                d.send_keys(keyword)
                time.sleep(1)
                
                # 3. 엔터
                d.press("enter")
                time.sleep(8)
                
                # 4. 결과 확인
                clear_popups(d)
                screen_text = read_screen_text(d, filename=f"{keyword}_{i}_top.png")
                
                # 오류 화면이면 재시도 로직
                if any(x in screen_text for x in ["problem", "RETRY", "400"]):
                    print("🧹 [복구] 400 에러 발견. 재시도.")
                    clear_popups(d)
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
