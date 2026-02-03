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
        except Exception as e:
            print(f"   ⚠️ 시트 저장 실패: {e}")

def read_screen_text(d, filename=None):
    try:
        temp_path = "current_screen.png"
        d.screenshot(temp_path)
        if filename:
            save_path = os.path.join(SCREENSHOT_DIR, filename)
            os.system(f"cp {temp_path} {save_path}")
        text = pytesseract.image_to_string(Image.open(temp_path), lang='kor+eng')
        return " ".join(text.split())
    except Exception as e:
        return ""

# ==========================================
# [기능] 유튜브 실행 (시크릿 모드 강력 대응)
# ==========================================
def setup_youtube(d):
    print("   🔨 크롬 강제 종료 및 유튜브 실행...")
    d.shell("am force-stop com.android.chrome")
    d.shell("am force-stop com.google.android.youtube") # 유튜브도 완전히 껐다 켬
    d.press("home")
    time.sleep(1)
    
    # 1. 유튜브 실행
    d.app_start("com.google.android.youtube")
    # 앱이 뜰 때까지 넉넉히 대기 (Verify age 화면이 뜰 수도 있음)
    time.sleep(10)
    
    # 2. 팝업(Premium/로그인) 닫기 시도 (영어+한국어)
    if d(text="Skip trial").exists: d(text="Skip trial").click()
    if d(text="무료 체험 건너뛰기").exists: d(text="무료 체험 건너뛰기").click()
    if d(text="No thanks").exists: d(text="No thanks").click()
    if d(text="나중에").exists: d(text="나중에").click()
    
    # "Verify your age" 가 뜨면 뒤로가기 한번 눌러보기
    screen_text = read_screen_text(d)
    if "Verify" in screen_text or "인증" in screen_text:
        print("   ⚠️ 연령/로그인 인증 화면 감지 -> 뒤로가기 시도")
        d.press("back")
        time.sleep(2)

    # 3. 시크릿 모드 진입
    print("   🕵️ 시크릿 모드 진입 시도...")
    
    # 프로필 아이콘 찾기 (ID로 찾기)
    # 로그인 안 된 상태면 'person' 아이콘일 수 있음
    if d(resourceId="com.google.android.youtube:id/mobile_user_account_image").exists:
        d(resourceId="com.google.android.youtube:id/mobile_user_account_image").click()
        print("      -> 프로필 아이콘 클릭")
    elif d(description="Account").exists:
         d(description="Account").click()
    elif d(description="계정").exists:
         d(description="계정").click()
    else:
        # 못 찾으면 좌표(우상단) 강제 클릭
        print("      -> 프로필 못 찾음, 좌표 강제 클릭")
        d.click(0.92, 0.05)
    
    time.sleep(2)
    
    # 시크릿 모드 메뉴 클릭 (ID 또는 텍스트 2가지 모두 체크)
    # 영어: Turn on Incognito / 한국어: 시크릿 모드 사용
    if d(resourceId="com.google.android.youtube:id/new_incognito_session_item").exists:
        d(resourceId="com.google.android.youtube:id/new_incognito_session_item").click()
        print("      -> 시크릿 모드(ID) 클릭")
    elif d(text="Turn on Incognito").exists:
        d(text="Turn on Incognito").click()
        print("      -> Turn on Incognito 클릭")
    elif d(text="시크릿 모드 사용").exists:
        d(text="시크릿 모드 사용").click()
        print("      -> 시크릿 모드 사용 클릭")
    else:
        # 메뉴가 안 떴으면 한번 더 좌표 클릭 시도
        d.click(0.5, 0.35) 
    
    time.sleep(5)
    
    # "Got it" / "확인" 버튼
    if d(text="Got it").exists: d(text="Got it").click()
    if d(text="확인").exists: d(text="확인").click()

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 에뮬레이터 연결...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        setup_youtube(d)

        for keyword in KEYWORDS:
            print(f"\n🔎 [{keyword}] 검색 시작")
            
            for i in range(1, REPEAT_COUNT + 1):
                sys.stdout.flush()
                print(f"   [{i}/{REPEAT_COUNT}] 진행 중...", end=" ")
                
                # ★ [수정] 유튜브 앱 체크 로직 완화
                # Verify age 같은 웹뷰가 뜨면 패키지명이 바뀔 수 있음.
                # 즉시 재실행하지 않고, 일단 뒤로가기를 눌러서 복구 시도
                current_app = d.app_current()
                if current_app['package'] != "com.google.android.youtube":
                    print(f"⚠️ 현재 앱({current_app['package']})이 유튜브가 아님. 뒤로가기 시도...")
                    d.press("back")
                    time.sleep(2)
                    
                    # 그래도 아니면 재실행
                    current_app = d.app_current()
                    if current_app['package'] != "com.google.android.youtube":
                        print("⚠️ 여전히 아님. 유튜브 강제 재실행.")
                        d.app_start("com.google.android.youtube")
                        time.sleep(5)

                # 검색 버튼 클릭 (ID 기반)
                if d(resourceId="com.google.android.youtube:id/menu_item_search").exists:
                    d(resourceId="com.google.android.youtube:id/menu_item_search").click()
                elif d(description="Search", packageName="com.google.android.youtube").exists:
                    d(description="Search", packageName="com.google.android.youtube").click()
                elif d(description="검색", packageName="com.google.android.youtube").exists:
                    d(description="검색", packageName="com.google.android.youtube").click()
                else:
                    # 검색 버튼이 안 보이면(이미 검색창이거나 등등) 좌표 클릭은 위험하니 스킵하고 로그만
                    print("❌ 검색 버튼 못 찾음 (재시도)")
                    continue
                
                time.sleep(2)
                
                # 검색어 입력
                d.clear_text()
                d.send_keys(keyword)
                time.sleep(1)
                d.press("enter")
                time.sleep(8)
                
                screen_text = read_screen_text(d, filename=f"{keyword}_{i}_top.png")
                
                # 로그인 팝업 청소 (Sign in / Verify / 인증 / 로그인)
                if any(x in screen_text for x in ["Sign in", "wi Googl", "Account", "Verify", "인증", "로그인"]):
                    print(f"🧹 [청소] 방해 팝업 발견! 뒤로가기.")
                    d.press("back") 
                    time.sleep(2)
                    screen_text = read_screen_text(d, filename=f"{keyword}_{i}_retry.png")
                
                d.swipe(500, 1500, 500, 500, 0.3) 
                time.sleep(2)
                
                is_ad = "X"
                ad_text = "-"
                
                if any(x in screen_text for x in ["광고", "Ad", "Sponsored"]):
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
