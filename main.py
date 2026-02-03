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
            worksheet.clear() 
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
        clean_text = " ".join(text.split())
        return clean_text
    except Exception as e:
        return ""

# ==========================================
# [기능] 크롬 초기 설정 강제 스킵
# ==========================================
def skip_chrome_welcome(d):
    print("   🔨 크롬 설정 건너뛰기...")
    d.app_start("com.android.chrome")
    time.sleep(5)
    
    # 약관 동의
    if d(text="Accept & continue").exists:
        d(text="Accept & continue").click()
    elif d(resourceId="com.android.chrome:id/terms_accept").exists:
        d(resourceId="com.android.chrome:id/terms_accept").click()
        
    time.sleep(3)
    
    # 로그인 거절
    if d(text="No thanks").exists:
        d(text="No thanks").click()
    elif d(resourceId="com.android.chrome:id/negative_button").exists:
        d(resourceId="com.android.chrome:id/negative_button").click()
    else:
        d.click(0.25, 0.9) # 좌측 하단 강제 클릭

# ==========================================
# [기능] IP 확인 (브라우저)
# ==========================================
def check_ip_browser(d):
    print("🌐 IP 위치 확인 중...")
    skip_chrome_welcome(d)
    
    d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io/json" -p com.android.chrome')
    time.sleep(10)
    
    screen_text = read_screen_text(d, filename="ip_check_final.png")
    
    if "KR" in screen_text or "Korea" in screen_text:
        print(f"   ✅ [성공] 한국 IP 확인됨!")
    elif "US" in screen_text:
        print(f"   ⚠️ [주의] 미국 IP입니다.")
    else:
        print(f"   ℹ️ (참고) 화면 내용: {screen_text[:50]}...")

# ==========================================
# [기능] 유튜브 실행 (순정 앱 터치 방식)
# ==========================================
def setup_youtube(d):
    print("   🔨 크롬 강제 종료 및 유튜브 실행...")
    d.shell("am force-stop com.android.chrome") # 크롬 죽이기
    d.press("home")
    time.sleep(1)
    
    # 1. 앱 실행
    d.app_start("com.google.android.youtube")
    time.sleep(8)
    
    # 2. 팝업(Premium 권유 등) 닫기 시도
    if d(text="Skip trial").exists:
        d(text="Skip trial").click()
    if d(text="No thanks").exists:
        d(text="No thanks").click()
    d.click(0.5, 0.9) # 혹시 모르니 하단 빈공간 클릭

    # 3. 시크릿 모드 진입
    print("   🕵️ 시크릿 모드 진입...")
    # 프로필 아이콘 클릭 (ID로 찾기 시도)
    if d(resourceId="com.google.android.youtube:id/mobile_user_account_image").exists:
        d(resourceId="com.google.android.youtube:id/mobile_user_account_image").click()
    else:
        # 못 찾으면 좌표(우상단)
        d.click(0.92, 0.05)
    
    time.sleep(2)
    
    # 시크릿 모드 메뉴 클릭
    if d(text="Turn on Incognito").exists:
        d(text="Turn on Incognito").click()
    elif d(text="시크릿 모드 사용").exists:
        d(text="시크릿 모드 사용").click()
    else:
        # 좌표(메뉴 중간쯤)
        d.click(0.5, 0.35) 
    
    time.sleep(5)
    
    # "Got it" 확인 버튼
    if d(text="Got it").exists:
        d(text="Got it").click()
    else:
        d.click(0.5, 0.9)

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 에뮬레이터 연결...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        check_ip_browser(d)
        setup_youtube(d)

        for keyword in KEYWORDS:
            print(f"\n🔎 [{keyword}] 검색 시작 (앱 터치 방식)")
            
            for i in range(1, REPEAT_COUNT + 1):
                sys.stdout.flush()
                print(f"   [{i}/{REPEAT_COUNT}] 진행 중...", end=" ")
                
                # ====================================================
                # ★ [핵심] URL 실행 대신 '돋보기' 버튼 누르고 타이핑
                # ====================================================
                
                # 1. 돋보기 버튼(검색) 클릭
                # (보통 ID: menu_item_search 또는 설명: Search)
                if d(description="Search").exists:
                    d(description="Search").click()
                elif d(resourceId="com.google.android.youtube:id/menu_item_search").exists:
                    d(resourceId="com.google.android.youtube:id/menu_item_search").click()
                elif d(description="검색").exists:
                    d(description="검색").click()
                else:
                    # 못 찾으면 우측 상단 돋보기 위치 강제 클릭
                    d.click(0.85, 0.05)
                
                time.sleep(2)
                
                # 2. 검색어 입력
                d.clear_text() # 기존 검색어 삭제
                d.send_keys(keyword)
                time.sleep(1)
                
                # 3. 엔터키 입력 (검색 실행)
                d.press("enter")
                
                # 4. 결과 로딩 대기
                time.sleep(8)
                
                # 상단 캡처
                screen_text = read_screen_text(d, filename=f"{keyword}_{i}_top.png")
                
                # 스크롤
                d.swipe(500, 1500, 500, 500, 0.3) 
                time.sleep(2)
                
                is_ad = "X"
                ad_text = "-"
                
                # 크롬이 튀어나오면 다시 죽임
                if "Sign in" in screen_text or "Chrome" in screen_text:
                     print(f"❌ [오류] 크롬이 방해함. 강제 종료.")
                     d.shell("am force-stop com.android.chrome")
                elif "광고" in screen_text or "Ad" in screen_text or "Sponsored" in screen_text:
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
                
                # 다음 검색을 위해 뒤로가기 두 번 (검색 목록 -> 홈)
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
