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
# [설정] 키워드 제한 (요청사항)
# ==========================================
ADB_ADDR = "emulator-5554" 
KEYWORDS = ["해커스"] # ★ 요청대로 해커스만 남김
REPEAT_COUNT = 10 
SCREENSHOT_DIR = "screenshots"

# ==========================================
# [함수] 광고주 분류 (선생님 코드 이식)
# ==========================================
def classify_advertiser(text):
    """OCR 텍스트를 분석하여 광고주와 세부 브랜드를 분류"""
    clean_text = text.replace(" ", "")
    
    # 1. 타사 광고 식별
    if "해커스" not in clean_text and "Hackers" not in clean_text:
        # 타사인데 공무원/자격증 관련 키워드가 보이면 경쟁사로 분류
        if any(x in clean_text for x in ["에듀윌", "공단기", "메가", "박문각", "YBM", "파고다", "영단기", "시원스쿨", "야나두"]):
            return "경쟁사", text[:30] # 상세 내용
        return "타사", text[:30]

    # 2. 해커스 내부 분류
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
# [기능] 구글 시트 (초기화 기능 포함)
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
            # ★ 요청사항: 시트가 있으면 내용 초기화하고 헤더 다시 씀
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
                data["시간"], 
                data["키워드"], 
                data["회차"], 
                data["광고여부"], 
                data["광고주_구분"], 
                data["상세_광고주"],
                data["광고형태"],
                data["제목/텍스트"]
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
    """방해꾼 제거 (이미지 1, 4 등 대응)"""
    try:
        # 크롬/구글 로그인 (이미지 1)
        if d(textContains="Welcome").exists:
             if d(textContains="Accept").exists: d(textContains="Accept").click()
        if d(textContains="Turn on sync").exists:
             if d(textContains="No thanks").exists: d(textContains="No thanks").click()
        if d(textContains="Add account").exists: # 이미지 5b841c 대응
             if d(textContains="Use without").exists: d(textContains="Use without").click()

        # 유튜브 팝업
        if d(textContains="Try searching").exists: # 검색 유도 팝업
             d.click(0.5, 0.2) # 배경 클릭해서 닫기
        
        # 키보드 설정
        if d(textContains="better keyboard").exists:
            d(textContains="No").click()
            
        # 자막/업데이트 등 (이미지 4)
        if d(textContains="Captions").exists:
            d.click(0.5, 0.2) # 화면 상단 빈곳 클릭
    except: pass

# ==========================================
# [1단계] IP 확인 (크롬 설정 스킵 강화)
# ==========================================
def check_ip_browser(d):
    print("🌐 IP 확인 시작...")
    d.shell("am force-stop com.android.chrome")
    d.app_start("com.android.chrome", stop=True)
    time.sleep(5)
    
    nuke_popups(d) # Welcome 화면 처리
    
    d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io/json" -p com.android.chrome')
    time.sleep(15)
    
    nuke_popups(d)
    read_screen_text(d, filename="DEBUG_1_IP.png")

# ==========================================
# [2단계] 유튜브 준비 (시크릿 모드 재시도 로직)
# ==========================================
def setup_youtube(d):
    print("   🧹 유튜브 초기화...")
    d.shell("pm clear com.google.android.youtube")
    time.sleep(3)
    d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
    time.sleep(15)
    nuke_popups(d)
    
    # 400 에러 체크 (스샷만)
    d.screenshot(os.path.join(SCREENSHOT_DIR, "DEBUG_2_YOUTUBE.png"))

    print("   🕵️ 시크릿 모드 진입 시도...")
    
    # 우상단 프로필 아이콘 클릭 (가장 확실)
    d.click(0.92, 0.05)
    time.sleep(2)
    
    # 메뉴가 떴는지 확인
    if d(textContains="Turn on Incognito").exists:
        d(textContains="Turn on Incognito").click()
        print("   ✅ 시크릿 모드 켜기 성공")
    elif d(resourceId="com.google.android.youtube:id/new_incognito_session_item").exists:
        d(resourceId="com.google.android.youtube:id/new_incognito_session_item").click()
        print("   ✅ 시크릿 모드 켜기 성공 (ID)")
    else:
        # 로그인 버튼이 떠서 메뉴가 안 보일 경우 (이미지 5b8494)
        if d(textContains="Sign in").exists and d(textContains="Settings").exists:
             print("   ⚠️ 로그인 유도 화면 -> 닫기 시도")
             d.press("back") # 뒤로가기 후 다시 시도
             time.sleep(1)
             d.click(0.92, 0.05) # 다시 프로필 클릭
             time.sleep(1)
             if d(textContains="Turn on Incognito").exists:
                d(textContains="Turn on Incognito").click()

    time.sleep(5)
    if d(text="Got it").exists: d(text="Got it").click()

# ==========================================
# [3단계] 검색 및 분석 (입력 보장 + 랜덤클릭 삭제)
# ==========================================
def perform_search_and_analyze(d, keyword, worksheet, count):
    print(f"\n🔎 [{count}] '{keyword}' 검색 시작...")
    
    # 1. 돋보기 클릭
    if d(description="Search").exists: d(description="Search").click()
    elif d(resourceId="com.google.android.youtube:id/menu_item_search").exists: d(resourceId="com.google.android.youtube:id/menu_item_search").click()
    else: d.click(0.85, 0.05) # 우상단 강제 클릭
    
    time.sleep(2)
    nuke_popups(d) # 키보드 팝업 제거
    
    # 2. ★ [핵심] 텍스트 입력 확인 사살
    # 텍스트가 실제로 들어갔는지 확인하고 안 들어갔으면 재시도
    print(f"   ⌨️ '{keyword}' 입력 시도...")
    
    # 방법 A: set_text (가장 빠름)
    search_box = d(resourceId="com.google.android.youtube:id/search_edit_text")
    if search_box.exists:
        search_box.set_text(keyword)
    else:
        d.shell(f"input text '{keyword}'")
        
    time.sleep(1)
    
    # 입력 확인
    current_text = ""
    if search_box.exists:
        current_text = search_box.get_text()
    
    # 비어있으면 ADB로 재입력
    if not current_text or current_text == "Search YouTube":
        print("   ⚠️ 입력 실패 감지 -> ADB로 재입력")
        d.shell(f"input text '{keyword}'")
        time.sleep(1)

    # 3. ★ [핵심] 엔터 입력 (좌표 클릭 삭제함!)
    print("   🚀 검색 실행 (ENTER)...")
    d.press("enter")
    time.sleep(1)
    d.shell("input keyevent 66") # 한번 더 확실하게
    
    time.sleep(8) # 로딩 대기
    
    # 4. 결과 분석 (OCR)
    print("   📸 결과 분석 중...")
    screen_text = read_screen_text(d, filename=f"{keyword}_{count}.png")
    
    # 데이터 추출
    is_ad = "X"
    ad_corp = "-"     
    ad_detail = "-"   
    ad_type = "-"     
    ad_title = "-"    
    
    # 광고 키워드 찾기
    if "Ad" in screen_text or "광고" in screen_text or "Sponsored" in screen_text:
        is_ad = "O"
        
        # 광고 형태 추측
        if "조회수" in screen_text or "views" in screen_text:
            ad_type = "영상광고"
        else:
            ad_type = "배너/검색광고"
            
        # 제목 추정 (OCR 텍스트 중 상위 라인)
        lines = [line for line in screen_text.split('\n') if len(line) > 5]
        for line in lines:
            if "광고" not in line and "Ad" not in line:
                ad_title = line
                break
        
        # ★ 선생님의 분류 로직 적용
        ad_corp, ad_detail = classify_advertiser(screen_text)
        
        print(f"   🚨 광고 발견! [{ad_corp}] {ad_title[:15]}...")
    else:
        print("   ❌ 광고 없음")
        
    # 5. 시트 저장
    data = {
        "시간": datetime.now().strftime('%H:%M:%S'),
        "키워드": keyword,
        "회차": count,
        "광고여부": is_ad,
        "광고주_구분": ad_corp,
        "상세_광고주": ad_detail,
        "광고형태": ad_type,
        "제목/텍스트": ad_title
    }
    append_to_sheet(worksheet, data)
    
    # 6. 복귀 (검색어 지우기 위해 X 버튼 누르거나 뒤로가기)
    d.press("back")
    time.sleep(1)
    d.press("back") # 목록 -> 홈
    time.sleep(2)

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 모니터링 시작 (해커스 전용)...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        check_ip_browser(d)
        setup_youtube(d)

        for keyword in KEYWORDS:
            for i in range(1, REPEAT_COUNT + 1):
                # 앱 이탈 체크
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
