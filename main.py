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
KEYWORDS = ["해커스"] # 일단 해커스만 테스트
REPEAT_COUNT = 10 
SCREENSHOT_DIR = "screenshots"

# ==========================================
# [함수] 광고주 분류
# ==========================================
def classify_advertiser(text):
    clean_text = text.replace(" ", "")
    if "해커스" not in clean_text and "Hackers" not in clean_text:
        if any(x in clean_text for x in ["에듀윌", "공단기", "메가", "박문각", "YBM", "파고다", "영단기", "시원스쿨", "야나두"]):
            return "경쟁사", text[:30]
        return "타사", text[:30]

    if "공무원" in clean_text: return "해커스공무원", "해커스"
    if "경찰" in clean_text: return "해커스경찰", "해커스"
    if "소방" in clean_text: return "해커스소방", "해커스"
    if "자격증" in clean_text or "기사" in clean_text: return "해커스자격증", "해커스"
    if "공인중개사" in clean_text or "주택" in clean_text: return "해커스공인중개사", "해커스"
    if "금융" in clean_text: return "해커스금융", "해커스"
    if "잡" in clean_text or "취업" in clean_text or "면접" in clean_text: return "해커스잡", "해커스"
    if "편입" in clean_text: return "해커스편입", "해커스"
    if "어학" in clean_text or "토익" in clean_text or "텝스" in clean_text or "토스" in clean_text or "오픽" in clean_text: return "해커스어학", "해커스"
    
    return "해커스(기타)", "해커스"

# ==========================================
# [기능] 구글 시트
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
        header = ["시간", "키워드", "회차", "광고여부", "광고주_구분", "상세_광고주", "광고형태", "제목/텍스트"]
        
        try:
            worksheet = sh.worksheet(sheet_name)
            print(f"   📄 기존 시트 '{sheet_name}' 초기화...")
            worksheet.clear()
            worksheet.append_row(header)
        except:
            print(f"   📄 새 시트 '{sheet_name}' 생성...")
            worksheet = sh.add_worksheet(title=sheet_name, rows="1000", cols="20")
            worksheet.append_row(header)
            
        return worksheet
    except Exception as e:
        print(f"❌ 구글 시트 연결 실패: {e}")
        return None

def append_to_sheet(worksheet, data):
    if worksheet:
        try:
            row = [
                data["시간"], data["키워드"], data["회차"], 
                data["광고여부"], data["광고주_구분"], data["상세_광고주"],
                data["광고형태"], data["제목/텍스트"]
            ]
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

def nuke_popups(d):
    """방해꾼 제거"""
    try:
        if d(textContains="Accept").exists: d(textContains="Accept").click()
        if d(textContains="No thanks").exists: d(textContains="No thanks").click()
        if d(textContains="better keyboard").exists: d(textContains="No").click()
        if d(text="Skip trial").exists: d(text="Skip trial").click()
        # 기록 일시 중지 확인 팝업
        if d(textContains="Pause").exists and d(textContains="history").exists:
             d(text="Pause").click()
    except: pass

# ==========================================
# [1단계] IP 확인
# ==========================================
def check_ip_browser(d):
    print("🌐 IP 확인 시작...")
    d.shell("am force-stop com.android.chrome")
    d.app_start("com.android.chrome", stop=True)
    time.sleep(5)
    nuke_popups(d)
    d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io/json" -p com.android.chrome')
    time.sleep(15)
    nuke_popups(d)
    read_screen_text(d, filename="DEBUG_1_IP.png")

# ==========================================
# [2단계] 유튜브 설정 (기록 일시 중지)
# ==========================================
def setup_youtube_no_history(d):
    print("   🧹 유튜브 앱 데이터 초기화...")
    d.shell("pm clear com.google.android.youtube")
    time.sleep(3)
    
    print("   🔨 유튜브 실행...")
    d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
    time.sleep(12)
    nuke_popups(d)
    
    print("   ⚙️ [설정] 기록 일시 중지 적용 중...")
    
    # 1. 프로필 아이콘 클릭 (우상단)
    d.click(0.92, 0.05)
    time.sleep(2)
    
    # 2. Settings 클릭
    if d(text="Settings").exists:
        d(text="Settings").click()
    else:
        # 메뉴가 안 보이면 스크롤
        d.swipe(0.5, 0.8, 0.5, 0.2)
        if d(text="Settings").exists: d(text="Settings").click()
        
    time.sleep(2)
    
    # 3. History & privacy 클릭
    if d(textContains="History").exists:
        d(textContains="History").click()
    
    time.sleep(2)
    
    # 4. Pause watch history (스위치 켜기)
    if d(textContains="Pause watch history").exists:
        d(textContains="Pause watch history").click()
        time.sleep(1)
        if d(text="Pause").exists: d(text="Pause").click() # 확인 팝업
        
    # 5. Pause search history (스위치 켜기)
    if d(textContains="Pause search history").exists:
        d(textContains="Pause search history").click()
        time.sleep(1)
        if d(text="Pause").exists: d(text="Pause").click() # 확인 팝업
        
    print("   ✅ 기록 일시 중지 완료")
    
    # 홈으로 복귀 (뒤로가기 연타)
    d.press("back")
    time.sleep(1)
    d.press("back")
    time.sleep(1)
    
    # 혹시 모르니 홈 버튼 클릭
    if d(description="Home").exists:
        d(description="Home").click()

# ==========================================
# [3단계] 검색 및 분석 (완전 개편)
# ==========================================
def perform_search_and_analyze(d, keyword, worksheet, count):
    print(f"\n🔎 [{count}] '{keyword}' 검색 시작...")
    
    # 1. 돋보기 클릭
    if d(description="Search").exists: 
        d(description="Search").click()
    elif d(resourceId="com.google.android.youtube:id/menu_item_search").exists: 
        d(resourceId="com.google.android.youtube:id/menu_item_search").click()
    else: 
        d.click(0.85, 0.05) # 우상단 강제
    
    time.sleep(2)
    nuke_popups(d)
    
    # 2. ★ [핵심] 기존 검색어 삭제 (2회차부터 필수)
    # 검색창 X버튼(Clear)이 있으면 누르고, 없으면 텍스트 비우기
    search_box = d(resourceId="com.google.android.youtube:id/search_edit_text")
    
    if search_box.exists:
        # X 버튼 확인
        if d(resourceId="com.google.android.youtube:id/search_clear_button").exists:
            print("   🧹 기존 검색어 삭제 (X 버튼)")
            d(resourceId="com.google.android.youtube:id/search_clear_button").click()
        else:
            search_box.clear_text()
    
    time.sleep(1)
    
    # 3. 검색어 입력 (복사 붙여넣기 효과)
    print(f"   ⌨️ '{keyword}' 입력 (주입)...")
    if search_box.exists:
        search_box.set_text(keyword) # uiautomator2 set_text가 가장 확실함
    else:
        d.shell(f"input text '{keyword}'")
        
    time.sleep(2)
    
    # 4. ★ [핵심] 엔터 입력 (좌표 클릭 절대 금지!)
    print("   🚀 검색 실행 (시스템 엔터)...")
    # 키보드 엔터키(66) 전송 -> 가장 안전한 방법
    d.shell("input keyevent 66") 
    
    time.sleep(8) # 로딩 대기
    
    # 5. 결과 분석
    screen_text = read_screen_text(d, filename=f"{keyword}_{count}.png")
    
    is_ad = "X"
    ad_corp, ad_detail, ad_type, ad_title = "-", "-", "-", "-"
    
    if "Ad" in screen_text or "광고" in screen_text or "Sponsored" in screen_text:
        is_ad = "O"
        if "조회수" in screen_text or "views" in screen_text: ad_type = "영상광고"
        else: ad_type = "배너/검색광고"
            
        lines = [line for line in screen_text.split('\n') if len(line) > 5]
        for line in lines:
            if "광고" not in line and "Ad" not in line:
                ad_title = line
                break
        
        ad_corp, ad_detail = classify_advertiser(screen_text)
        print(f"   🚨 광고 발견! [{ad_corp}]")
    else:
        print("   ❌ 광고 없음")
        
    data = {
        "시간": datetime.now().strftime('%H:%M:%S'),
        "키워드": keyword, "회차": count, "광고여부": is_ad,
        "광고주_구분": ad_corp, "상세_광고주": ad_detail,
        "광고형태": ad_type, "제목/텍스트": ad_title
    }
    append_to_sheet(worksheet, data)
    
    # 6. 다음 검색 준비 (뒤로가기)
    # 뒤로가기를 눌러서 검색 목록이나 홈으로 이동
    if d(resourceId="com.google.android.youtube:id/search_clear_button").exists:
        # 키보드가 떠있거나 검색창 활성 상태면 닫기
        d.press("back") 
    d.press("back") # 결과 화면에서 나가기
    time.sleep(2)

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 모니터링 시작 (기록중지 모드)...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        check_ip_browser(d)
        
        # ★ 시크릿 모드 대신 '설정' 변경
        setup_youtube_no_history(d)

        for keyword in KEYWORDS:
            for i in range(1, REPEAT_COUNT + 1):
                if d.app_current()['package'] != "com.google.android.youtube":
                    d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
                    time.sleep(5)
                
                nuke_popups(d)
                perform_search_and_analyze(d, keyword, ws, i)
                
    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    run_android_monitoring()
