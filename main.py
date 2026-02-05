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
import uuid # 랜덤 ID 생성을 위해 필요

# ==========================================
# [설정]
# ==========================================
ADB_ADDR = "emulator-5554" 
KEYWORDS = ["해커스"] 
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
        header = ["시간", "키워드", "회차", "광고여부", "광고주_구분", "상세_광고주", "광고형태", "제목/텍스트", "Ad_ID"]
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
                data["광고형태"], data["제목/텍스트"], data["Ad_ID"]
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
    """초기화된 앱에서 뜨는 팝업 제거"""
    try:
        if d(textContains="Accept").exists: d(textContains="Accept").click()
        if d(textContains="No thanks").exists: d(textContains="No thanks").click()
        if d(textContains="better keyboard").exists: d(textContains="No").click()
        if d(textContains="Try searching").exists: d.click(0.5, 0.2)
        # 로그인 유도 팝업 무시 (좌상단 X 누르기 대신 그냥 닫기 시도)
        if d(textContains="Sign in").exists: 
             # SKIP 버튼이 있으면 클릭, 없으면 무시
             if d(textContains="Skip").exists: d(textContains="Skip").click()
    except: pass

# ==========================================
# [핵심] 랜덤 광고 ID 주입 (매번 신분 세탁)
# ==========================================
def inject_random_ad_id(d):
    # 매번 새로운 랜덤 UUID 생성
    random_id = str(uuid.uuid4())
    print(f"   🎭 [신분세탁] 새로운 Advertising ID 발급: {random_id}")
    
    d.shell(f"settings put global google_ad_id {random_id}")
    d.shell("settings put global ad_id_enabled 1")
    d.shell("settings put secure limit_ad_tracking 0")
    return random_id

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
# [설정] 유튜브 완전 초기화 실행
# ==========================================
def setup_youtube_fresh(d):
    print("   🧹 유튜브 앱 데이터 완전 삭제 (시크릿 효과)...")
    d.shell("pm clear com.google.android.youtube") 
    time.sleep(2)
    
    # ★ 랜덤 ID 주입
    current_ad_id = inject_random_ad_id(d)
    
    print("   🔨 유튜브 실행...")
    d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
    time.sleep(10)
    
    # 초기 실행 시 뜨는 '알림 허용', '로그인' 팝업 처리
    if d(textContains="Allow").exists: d(textContains="Allow").click()
    if d(textContains="Sign in").exists: 
        # 로그인 팝업이 뜨면 바깥쪽 클릭하거나 닫기 시도 안 해도 됨 (검색 누르면 사라짐)
        pass
        
    return current_ad_id

# ==========================================
# [3단계] 검색 및 분석
# ==========================================
def perform_search_and_analyze(d, keyword, worksheet, count, current_ad_id):
    print(f"\n🔎 [{count}] '{keyword}' 검색 시작...")
    
    # 1. 돋보기 클릭
    # 앱 초기화 직후에는 상단에 돋보기가 바로 보임
    if d(description="Search").exists: 
        d(description="Search").click()
    elif d(resourceId="com.google.android.youtube:id/menu_item_search").exists: 
        d(resourceId="com.google.android.youtube:id/menu_item_search").click()
    else: 
        d.click(0.85, 0.05) # 우상단
    
    time.sleep(2)
    nuke_popups(d)
    
    # 2. 검색어 입력 (커서 잡고 입력)
    search_box = d(resourceId="com.google.android.youtube:id/search_edit_text")
    if search_box.exists:
        search_box.click()
        time.sleep(1)
        # 초기화 상태라 기존 텍스트 없음
        
    print(f"   ⌨️ '{keyword}' 입력...")
    d.shell(f"input text '{keyword}'")
    time.sleep(2)
    
    # 3. 엔터
    print("   🚀 검색 실행...")
    d.shell("input keyevent 66") 
    
    print("   ⏳ 광고 로딩 대기 (10초)...")
    time.sleep(10)
    
    # 4. 화면 정리 (키보드 닫기)
    d.press("back") 
    time.sleep(1)
    d.swipe(0.5, 0.3, 0.5, 0.8, 0.3) # 맨 위로
    time.sleep(2)
    
    # 5. 결과 분석
    screen_text = read_screen_text(d, filename=f"{keyword}_{count}.png")
    
    is_ad = "X"
    ad_corp, ad_detail, ad_type, ad_title = "-", "-", "-", "-"
    
    # 광고 키워드 (방문하기, 설치하기 등 추가)
    if any(x in screen_text for x in ["Ad", "Sponsored", "광고", "Promoted", "방문하기", "설치하기"]):
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
        "광고형태": ad_type, "제목/텍스트": ad_title,
        "Ad_ID": current_ad_id
    }
    append_to_sheet(worksheet, data)

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 모니터링 시작 (무한 초기화 모드)...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        check_ip_browser(d)
        
        for keyword in KEYWORDS:
            for i in range(1, REPEAT_COUNT + 1):
                print(f"\n🔄 [Reset] {i}회차 시작 전 데이터 초기화...")
                # ★ 핵심: 매 회차마다 앱을 초기화하고 새로운 ID를 부여함
                # 이것이 '비로그인 시크릿 모드'와 동일한 효과를 냄
                current_ad_id = setup_youtube_fresh(d)
                
                nuke_popups(d)
                perform_search_and_analyze(d, keyword, ws, i, current_ad_id)
                
    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    run_android_monitoring()
