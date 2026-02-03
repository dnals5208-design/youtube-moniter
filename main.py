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

# ★ [핵심] 웰컴 화면/로그인 화면 무조건 패스
def handle_welcome_screens(d):
    # 크롬/유튜브 공통 약관 동의
    if d(text="Accept & continue").exists:
        print("   🔨 약관 동의(Accept) 클릭")
        d(text="Accept & continue").click()
        time.sleep(2)
    
    # 로그인 거절 (No thanks)
    if d(text="No thanks").exists:
        print("   🔨 로그인 거절(No thanks) 클릭")
        d(text="No thanks").click()
        time.sleep(2)

    # 유튜브 프리미엄 건너뛰기
    if d(text="Skip trial").exists: d(text="Skip trial").click()
    if d(text="무료 체험 건너뛰기").exists: d(text="무료 체험 건너뛰기").click()

def setup_youtube_pure_app(d):
    print("   🔨 유튜브 앱 실행 및 시크릿 모드 진입...")
    
    # 1. 크롬 죽이고 유튜브 실행
    d.shell("am force-stop com.android.chrome")
    d.app_start("com.google.android.youtube", stop=True)
    time.sleep(10)
    
    # 2. 방해꾼 제거
    handle_welcome_screens(d)
    
    # 3. 시크릿 모드 진입 시도 (최대 3회 재시도)
    for attempt in range(3):
        print(f"   🕵️ 시크릿 모드 진입 시도 ({attempt+1}/3)...")
        
        # 이미 시크릿 모드인지 확인 (상단에 'Incognito' 아이콘 혹은 텍스트)
        if d(description="Incognito profile").exists:
             print("   ✅ 이미 시크릿 모드입니다.")
             return

        # 프로필 아이콘 클릭
        if d(resourceId="com.google.android.youtube:id/mobile_user_account_image").exists:
            d(resourceId="com.google.android.youtube:id/mobile_user_account_image").click()
        elif d(description="Account").exists:
            d(description="Account").click()
        else:
            # 못 찾으면 우상단 좌표 클릭
            d.click(0.92, 0.05)
        
        time.sleep(2)
        
        # 메뉴 클릭
        if d(resourceId="com.google.android.youtube:id/new_incognito_session_item").exists:
            d(resourceId="com.google.android.youtube:id/new_incognito_session_item").click()
            print("   ✅ 시크릿 모드 버튼 클릭 완료")
            time.sleep(5)
            # Got it 처리
            if d(text="Got it").exists: d(text="Got it").click()
            return
        elif d(text="Turn on Incognito").exists:
            d(text="Turn on Incognito").click()
            print("   ✅ Turn on Incognito 클릭 완료")
            time.sleep(5)
            if d(text="Got it").exists: d(text="Got it").click()
            return
            
        # 메뉴가 안 보이면 닫고 다시 시도
        d.press("back")
        time.sleep(1)

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 에뮬레이터 연결...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        # IP 체크 (크롬 웰컴 스크린 처리 포함)
        print("🌐 IP 확인 (크롬)...")
        d.app_start("com.android.chrome", stop=True)
        time.sleep(5)
        handle_welcome_screens(d) # 여기서 Welcome to Chrome 처리
        d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io/json"')
        time.sleep(8)
        ip_text = read_screen_text(d, filename="ip_check.png")
        if "KR" in ip_text or "Korea" in ip_text:
            print("   ✅ [IP확인] 한국 IP 맞음")
        else:
            print(f"   ℹ️ [IP확인] 텍스트: {ip_text[:50]}...")

        # 유튜브 앱 세팅
        setup_youtube_pure_app(d)

        for keyword in KEYWORDS:
            print(f"\n🔎 [{keyword}] 검색 시작")
            
            for i in range(1, REPEAT_COUNT + 1):
                sys.stdout.flush()
                print(f"   [{i}/{REPEAT_COUNT}] 진행 중...", end=" ")
                
                # 앱 튕김 방지 (유튜브 아니면 재실행)
                if d.app_current()['package'] != "com.google.android.youtube":
                    print("⚠️ 유튜브 앱 아님. 재실행...")
                    d.app_start("com.google.android.youtube")
                    time.sleep(5)

                # 검색 버튼 클릭 (ID 기반)
                if d(resourceId="com.google.android.youtube:id/menu_item_search").exists:
                    d(resourceId="com.google.android.youtube:id/menu_item_search").click()
                elif d(description="Search").exists:
                    d(description="Search").click()
                else:
                    print("❌ 검색 버튼 못 찾음")
                    d.press("back") # 혹시 이상한 화면일까봐
                    continue
                
                time.sleep(2)
                d.clear_text()
                d.send_keys(keyword)
                time.sleep(1)
                d.press("enter")
                time.sleep(8)
                
                screen_text = read_screen_text(d, filename=f"{keyword}_{i}_top.png")
                
                # 방해 팝업(로그인, Welcome) 처리
                if any(x in screen_text for x in ["Sign in", "Welcome", "Verify", "Account"]):
                    print("🧹 [청소] 팝업 감지 -> 뒤로가기")
                    d.press("back")
                    time.sleep(2)
                    screen_text = read_screen_text(d, filename=f"{keyword}_{i}_retry.png")

                # 결과 저장 로직
                d.swipe(500, 1500, 500, 500, 0.3) 
                time.sleep(2)
                
                is_ad = "X"
                ad_text = "-"
                if any(x in screen_text for x in ["광고", "Ad", "Sponsored"]):
                    is_ad = "O"
                    ad_text = "광고 발견"
                    if "해커스" in screen_text or "Hackers" in screen_text: ad_text = "해커스 광고"
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
                
                # 홈으로 복귀
                d.press("back")
                time.sleep(1)
                d.press("back")
                time.sleep(2)
                
    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    run_android_monitoring()
