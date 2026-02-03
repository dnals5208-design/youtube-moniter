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

def setup_youtube_initial(d):
    print("   🔨 유튜브 초기화 및 시크릿 모드 진입 시도...")
    d.shell("am force-stop com.google.android.youtube")
    d.shell("am force-stop com.android.chrome")
    
    # 앱 실행
    d.app_start("com.google.android.youtube")
    time.sleep(10)
    
    # 초기 팝업 처리
    if d(text="Skip trial").exists: d(text="Skip trial").click()
    if d(text="무료 체험 건너뛰기").exists: d(text="무료 체험 건너뛰기").click()
    if d(text="No thanks").exists: d(text="No thanks").click()
    
    # 시크릿 모드 진입 (한번만 해두면 됨)
    print("   🕵️ 시크릿 모드 버튼 찾기...")
    if d(resourceId="com.google.android.youtube:id/mobile_user_account_image").exists:
        d(resourceId="com.google.android.youtube:id/mobile_user_account_image").click()
        time.sleep(2)
        if d(resourceId="com.google.android.youtube:id/new_incognito_session_item").exists:
            d(resourceId="com.google.android.youtube:id/new_incognito_session_item").click()
            print("   ✅ 시크릿 모드 진입 완료")
            time.sleep(4)
            if d(text="Got it").exists: d(text="Got it").click()
            if d(text="확인").exists: d(text="확인").click()

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 에뮬레이터 연결...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        setup_youtube_initial(d)

        for keyword in KEYWORDS:
            print(f"\n🔎 [{keyword}] 검색 시작")
            
            for i in range(1, REPEAT_COUNT + 1):
                sys.stdout.flush()
                print(f"   [{i}/{REPEAT_COUNT}] 진행 중...", end=" ")
                
                # ★ [핵심] Deep Link 사용: vnd.youtube://
                # 이 방식은 돋보기 버튼을 누를 필요가 없으며, 무조건 앱으로 연결됩니다.
                # 또한 검색어 입력 과정도 생략되어 훨씬 빠르고 정확합니다.
                cmd = f'am start -a android.intent.action.VIEW -d "vnd.youtube://results?search_query={keyword}"'
                d.shell(cmd)
                
                # 로딩 대기
                time.sleep(8)
                
                # 만약 "Nexus Launcher" 상태라면(앱 튕김), 다시 실행
                current_app = d.app_current()
                if current_app['package'] != "com.google.android.youtube":
                    print(f"⚠️ 앱 튕김 감지. 재시도...")
                    d.shell(cmd) # 명령어 재전송
                    time.sleep(10)
                
                screen_text = read_screen_text(d, filename=f"{keyword}_{i}_top.png")
                
                # 'There was a problem' (오류 화면) 처리
                if "problem" in screen_text or "오류" in screen_text or "Retry" in screen_text:
                     print("⚠️ 네트워크 오류 화면 감지. '재시도' 클릭 시도.")
                     d.click(0.5, 0.5) # 화면 중앙 클릭
                     time.sleep(5)
                     screen_text = read_screen_text(d, filename=f"{keyword}_{i}_retry.png")

                # 로그인 팝업 청소
                if any(x in screen_text for x in ["Sign in", "wi Googl", "Account", "Verify", "인증", "로그인"]):
                    print(f"🧹 [청소] 로그인 팝업 제거")
                    d.press("back") 
                    time.sleep(2)
                    screen_text = read_screen_text(d, filename=f"{keyword}_{i}_clean.png")
                
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
                
                # 뒤로가기 누르지 않음! (다음 루프에서 바로 vnd.youtube 링크로 덮어씌움)
                # 이렇게 해야 앱이 안 꺼짐.
                
    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR)
    run_android_monitoring()
