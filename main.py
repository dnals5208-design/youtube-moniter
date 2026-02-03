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

def handle_google_blockers(d):
    """크롬/유튜브의 각종 로그인/약관 방해꾼을 처리"""
    # 1. 크롬 약관 (Accept & continue)
    if d(text="Accept & continue").exists:
        print("   🔨 [방해꾼] 약관 동의 클릭")
        d(text="Accept & continue").click()
        time.sleep(2)
    
    # 2. 크롬 로그인 권유 (No thanks / Use without account)
    if d(text="No thanks").exists:
        print("   🔨 [방해꾼] No thanks 클릭")
        d(text="No thanks").click()
    elif d(resourceId="com.android.chrome:id/negative_button").exists:
        print("   🔨 [방해꾼] 거절 버튼(ID) 클릭")
        d(resourceId="com.android.chrome:id/negative_button").click()
    elif d(text="Use without an account").exists:
        print("   🔨 [방해꾼] 계정 없이 사용 클릭")
        d(text="Use without an account").click()
        
    # 3. 유튜브 프리미엄/로그인 팝업
    if d(text="Skip trial").exists: d(text="Skip trial").click()
    if d(text="무료 체험 건너뛰기").exists: d(text="무료 체험 건너뛰기").click()
    if d(text="나중에").exists: d(text="나중에").click()

def check_ip_browser(d):
    print("🌐 IP 확인 (크롬 실행 중)...")
    d.shell("am force-stop com.android.chrome")
    d.app_start("com.android.chrome", stop=True)
    time.sleep(5)
    
    # 방해꾼 1차 제거
    handle_google_blockers(d)
    
    # URL 이동
    d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io/json" -p com.android.chrome')
    time.sleep(8)
    
    # 방해꾼 2차 제거 (혹시 사이트 들어가려는데 또 떴을까봐)
    handle_google_blockers(d)
    
    # ★ 요청하신 스크린샷 무조건 찍기
    print("📸 IP 확인 화면 캡처 중...")
    ip_text = read_screen_text(d, filename="DEBUG_IP_CHECK.png")
    
    if "KR" in ip_text or "Korea" in ip_text:
        print(f"   ✅ [IP확인 성공] 한국 IP 감지됨")
    else:
        print(f"   ⚠️ [IP확인 실패] 인식된 텍스트: {ip_text[:50]}...")
        # 실패했어도 죽지 않고 넘어갑니다. (유튜브가 중요하니까)

def setup_youtube_force(d):
    print("   🔨 유튜브 메인 화면 강제 진입...")
    d.shell("am force-stop com.android.chrome")
    d.shell("am force-stop com.google.android.youtube")
    time.sleep(2)
    
    # ★ [핵심] 그냥 실행이 아니라 '메인 액티비티'를 콕 집어서 실행
    # 이렇게 하면 팝업 위로 메인 화면이 뜰 확률이 높음
    d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
    time.sleep(10)
    
    handle_google_blockers(d)
    
    # 앱이 떴는지 패키지 확인
    current = d.app_current()
    print(f"   ℹ️ 현재 실행 중인 앱: {current['package']}")
    
    if current['package'] != "com.google.android.youtube":
        print("   ⚠️ 유튜브가 아님 (로그인 창 등). 뒤로가기 3번 연타로 탈출 시도...")
        d.press("back")
        time.sleep(1)
        d.press("back")
        time.sleep(1)
        d.press("back")
        time.sleep(2)
        # 다시 실행
        d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
        time.sleep(8)

    # 시크릿 모드 진입
    print("   🕵️ 시크릿 모드 진입 시도...")
    # 1. 프로필 아이콘 (ID 우선)
    if d(resourceId="com.google.android.youtube:id/mobile_user_account_image").exists:
        d(resourceId="com.google.android.youtube:id/mobile_user_account_image").click()
    elif d(description="Account").exists:
        d(description="Account").click()
    elif d(description="계정").exists:
        d(description="계정").click()
    else:
        # 못 찾으면 우상단 좌표
        d.click(0.92, 0.05)
    
    time.sleep(2)
    
    # 2. 메뉴 선택
    if d(resourceId="com.google.android.youtube:id/new_incognito_session_item").exists:
        d(resourceId="com.google.android.youtube:id/new_incognito_session_item").click()
    elif d(text="Turn on Incognito").exists:
        d(text="Turn on Incognito").click()
    elif d(text="시크릿 모드 사용").exists:
        d(text="시크릿 모드 사용").click()
    
    time.sleep(4)
    if d(text="Got it").exists: d(text="Got it").click()
    if d(text="확인").exists: d(text="확인").click()

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 에뮬레이터 연결...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        # 1. IP 확인 (스크린샷 저장)
        check_ip_browser(d)
        
        # 2. 유튜브 준비
        setup_youtube_force(d)

        for keyword in KEYWORDS:
            print(f"\n🔎 [{keyword}] 검색 시작")
            
            for i in range(1, REPEAT_COUNT + 1):
                sys.stdout.flush()
                print(f"   [{i}/{REPEAT_COUNT}] 진행 중...", end=" ")
                
                # ★ 앱 이탈 방지 로직 강화
                current = d.app_current()
                if current['package'] != "com.google.android.youtube":
                    print(f"⚠️ 앱 이탈 감지 (현재: {current['package']}). 유튜브 복귀...")
                    d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
                    time.sleep(5)

                # 검색 버튼 클릭
                if d(resourceId="com.google.android.youtube:id/menu_item_search").exists:
                    d(resourceId="com.google.android.youtube:id/menu_item_search").click()
                elif d(description="Search").exists:
                    d(description="Search").click()
                elif d(description="검색").exists:
                    d(description="검색").click()
                else:
                    # 검색 버튼이 없으면 이미 검색창이거나, 홈이 아닐 수 있음 -> 좌표 클릭 시도 (최후의 수단)
                    print("❌ 검색 버튼 ID 못 찾음. 좌표 클릭 시도.")
                    d.click(0.85, 0.05) # 우상단
                
                time.sleep(2)
                d.clear_text()
                d.send_keys(keyword)
                time.sleep(1)
                d.press("enter")
                time.sleep(8)
                
                # 결과 캡처
                screen_text = read_screen_text(d, filename=f"{keyword}_{i}_top.png")
                
                # 로그인 방해꾼 청소
                if any(x in screen_text for x in ["Sign in", "Google", "Account", "Verify", "인증"]):
                    print("🧹 [청소] 로그인 팝업 -> 뒤로가기")
                    d.press("back")
                    time.sleep(2)
                    screen_text = read_screen_text(d, filename=f"{keyword}_{i}_retry.png")

                # 스크롤 & 광고 판별
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
                
                # 홈으로 복귀 (뒤로가기 2번)
                d.press("back")
                time.sleep(1)
                d.press("back")
                time.sleep(2)
                
    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    run_android_monitoring()
