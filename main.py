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
            # 이어쓰기를 위해 clear는 제거하고 헤더 체크만 함
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
        except Exception as e:
            print(f"   ⚠️ 시트 저장 실패: {e}")

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
        # 공백 제거 및 정리
        clean_text = " ".join(text.split())
        return clean_text
    except Exception as e:
        return ""

# ==========================================
# [기능] IP 확인 (브라우저)
# ==========================================
def check_ip_browser(d):
    print("🌐 IP 위치 확인 중...")
    d.app_start("com.android.chrome")
    time.sleep(5)
    
    # 약관 동의 등 스킵
    if d(text="Accept & continue").exists:
        d(text="Accept & continue").click()
    
    d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io/json" -p com.android.chrome')
    time.sleep(10)
    
    screen_text = read_screen_text(d, filename="ip_check_final.png")
    
    if "KR" in screen_text or "Korea" in screen_text:
        print(f"   ✅ [성공] 한국 IP 확인됨! (이미지 확인 완료)")
    else:
        print(f"   ℹ️ IP 확인 결과: {screen_text[:50]}...")

# ==========================================
# [기능] 유튜브 실행 (앱 강제 고정)
# ==========================================
def setup_youtube(d):
    print("   🔨 크롬 강제 종료 및 유튜브 실행...")
    d.shell("am force-stop com.android.chrome") # 크롬 죽이기
    d.press("home")
    time.sleep(1)
    
    # 유튜브 실행
    d.app_start("com.google.android.youtube")
    time.sleep(8)
    
    # 팝업 닫기 시도
    if d(text="Skip trial").exists: d(text="Skip trial").click()
    if d(text="No thanks").exists: d(text="No thanks").click()
    d.click(0.5, 0.9)

    print("   🕵️ 시크릿 모드 진입...")
    if d(resourceId="com.google.android.youtube:id/mobile_user_account_image").exists:
        d(resourceId="com.google.android.youtube:id/mobile_user_account_image").click()
    else:
        # 못 찾으면 좌표 대신 UI 덤프해서 텍스트로 찾기 시도
        d(description="Account").click_exists(timeout=2)
    
    time.sleep(2)
    
    if d(text="Turn on Incognito").exists:
        d(text="Turn on Incognito").click()
    elif d(text="시크릿 모드 사용").exists:
        d(text="시크릿 모드 사용").click()
    
    time.sleep(5)
    if d(text="Got it").exists: d(text="Got it").click()
    else: d.click(0.5, 0.9)

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 에뮬레이터 연결...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        # IP 체크는 이미 확실하니 생략해도 되지만, 확인용으로 둠
        check_ip_browser(d)
        setup_youtube(d)

        for keyword in KEYWORDS:
            print(f"\n🔎 [{keyword}] 검색 시작")
            
            for i in range(1, REPEAT_COUNT + 1):
                sys.stdout.flush()
                print(f"   [{i}/{REPEAT_COUNT}] 진행 중...", end=" ")
                
                # ★ [핵심 1] 앱 이탈 방지: 현재 앱이 유튜브인지 확인
                current_app = d.app_current()
                if current_app['package'] != "com.google.android.youtube":
                    print("⚠️ 유튜브 앱 아님. 재실행합니다.")
                    d.app_start("com.google.android.youtube")
                    time.sleep(5)

                # ★ [핵심 2] 정확한 검색 버튼 찾기 (홈 화면 검색바 클릭 방지)
                # resourceId가 일치하는 경우에만 클릭
                if d(resourceId="com.google.android.youtube:id/menu_item_search").exists:
                    d(resourceId="com.google.android.youtube:id/menu_item_search").click()
                elif d(description="Search", packageName="com.google.android.youtube").exists:
                    # 패키지 이름이 유튜브인 'Search'만 클릭
                    d(description="Search", packageName="com.google.android.youtube").click()
                else:
                    print("❌ 검색 버튼 못 찾음 (재시도)")
                    continue
                
                time.sleep(2)
                
                # 검색어 입력
                d.clear_text()
                d.send_keys(keyword)
                time.sleep(1)
                d.press("enter")
                time.sleep(8)
                
                # 화면 인식
                screen_text = read_screen_text(d, filename=f"{keyword}_{i}_top.png")
                
                # 로그인 팝업 청소
                if "Sign in" in screen_text or "wi Googl" in screen_text or "Account" in screen_text:
                    print(f"🧹 [청소] 로그인 팝업 제거")
                    d.press("back") 
                    time.sleep(2)
                    screen_text = read_screen_text(d, filename=f"{keyword}_{i}_retry.png")
                
                d.swipe(500, 1500, 500, 500, 0.3) 
                time.sleep(2)
                
                is_ad = "X"
                ad_text = "-"
                
                if "광고" in screen_text or "Ad" in screen_text or "Sponsored" in screen_text:
                    is_ad = "O"
                    ad_text = "광고 발견"
                    for k in ["해커스", "에듀윌", "공단기", "메가", "경단기", "소방", "야나두", "시원스쿨", "YBM", "Hackers"]:
                        if k in screen_text:
                            ad_text = f"{k} 광고"
                            break
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
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR)
    run_android_monitoring()
