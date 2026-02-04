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
import re

# ==========================================
# [설정]
# ==========================================
ADB_ADDR = "emulator-5554" 
KEYWORDS = [
    "해커스", "토익", "경찰공무원", 
    "소방공무원", "공무원", "텝스", 
    "토익스피킹", "공인중개사", "토스"
]
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
        if any(x in clean_text for x in ["에듀윌", "공단기", "메가", "박문각", "YBM", "파고다", "영단기"]):
            return "경쟁사", text[:20] # 상세 내용 조금만
        return "타사", text[:20]

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
# [기능] 구글 시트 (초기화 기능 추가)
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
            # 순서: 시간, 키워드, 회차, 광고여부, 광고주_구분, 상세_광고주, 광고형태, 제목
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
    """모든 방해 요소 제거"""
    try:
        # 각종 동의 팝업
        if d(textContains="Accept").exists: d(textContains="Accept").click()
        if d(textContains="No thanks").exists: d(textContains="No thanks").click()
        if d(textContains="Allow").exists: d(textContains="Allow").click()
        
        # 키보드 설정 팝업
        if d(textContains="better keyboard").exists:
            d(textContains="No").click()
            
        # 유튜브 프리미엄/업데이트
        if d(textContains="Skip trial").exists: d(textContains="Skip trial").click()
        if d(textContains="Later").exists: d(textContains="Later").click()
        if d(textContains="Got it").exists: d(textContains="Got it").click()
    except: pass

# ==========================================
# [1단계] IP 확인 (심플하게)
# ==========================================
def check_ip_browser(d):
    print("🌐 IP 확인 중...")
    d.shell("am force-stop com.android.chrome")
    d.app_start("com.android.chrome", stop=True)
    time.sleep(5)
    nuke_popups(d)
    
    d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io/json" -p com.android.chrome')
    time.sleep(15)
    nuke_popups(d)
    read_screen_text(d, filename="DEBUG_1_IP.png")

# ==========================================
# [2단계] 유튜브 준비
# ==========================================
def setup_youtube(d):
    print("   🧹 유튜브 초기화...")
    d.shell("pm clear com.google.android.youtube")
    time.sleep(3)
    d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
    time.sleep(15)
    nuke_popups(d)
    
    # 400 에러 떠도 무시하고 진행 (검색이 중요)
    
    print("   🕵️ 시크릿 모드 진입...")
    # 최신 유튜브 UI 대응: 우하단 -> 시크릿
    d.click(0.9, 0.95) # 우하단 클릭
    time.sleep(3)
    
    # 로그인 버튼 찾기
    if d(textContains="Sign in").exists: d(textContains="Sign in").click()
    elif d(description="Account").exists: d(description="Account").click()
    else: d.click(0.92, 0.05) # 우상단
        
    time.sleep(2)
    if d(textContains="Turn on Incognito").exists:
        d(textContains="Turn on Incognito").click()
    
    time.sleep(5)
    if d(text="Got it").exists: d(text="Got it").click()

# ==========================================
# [3단계] 검색 및 분석 (핵심)
# ==========================================
def perform_search_and_analyze(d, keyword, worksheet, count):
    print(f"\n🔎 [{count}] '{keyword}' 검색 시작...")
    
    # 1. 돋보기 클릭
    if d(description="Search").exists: d(description="Search").click()
    elif d(resourceId="com.google.android.youtube:id/menu_item_search").exists: d(resourceId="com.google.android.youtube:id/menu_item_search").click()
    else: d.click(0.85, 0.05) # 우상단 강제 클릭
    
    time.sleep(2)
    nuke_popups(d) # 키보드 팝업 제거
    
    # 2. 검색어 입력 (ADB Input)
    # set_text 대신 adb input 사용 (더 확실함)
    d.shell(f"input text '{keyword}'")
    time.sleep(2)
    
    # 3. 엔터 입력 (좌표 클릭 삭제함 - 오작동 원인)
    print("   🚀 검색 실행 (ENTER)...")
    d.shell("input keyevent 66") # Enter Key
    time.sleep(2)
    d.press("search") # 한번 더 보장
    
    time.sleep(8) # 로딩 대기
    
    # 4. 결과 분석 (OCR)
    print("   📸 결과 분석 중...")
    screen_text = read_screen_text(d, filename=f"{keyword}_{count}.png")
    
    # 데이터 추출
    is_ad = "X"
    ad_corp = "-"     # 광고주 구분 (해커스공무원 등)
    ad_detail = "-"   # 상세 광고주
    ad_type = "-"     # 배너 vs 영상
    ad_title = "-"    # 제목
    
    # 광고 키워드 찾기
    if "Ad" in screen_text or "광고" in screen_text or "Sponsored" in screen_text:
        is_ad = "O"
        
        # 광고 형태 추측
        if "조회수" in screen_text or "views" in screen_text:
            ad_type = "영상광고"
        else:
            ad_type = "배너/검색광고"
            
        # 광고주 및 제목 분석 (선생님 로직 적용)
        # OCR 텍스트에서 의미 있는 줄만 추출
        lines = [line for line in screen_text.split('\n') if len(line) > 5]
        
        # 제목 추정 (보통 상단에 위치)
        for line in lines:
            if "광고" not in line and "Ad" not in line:
                ad_title = line
                break
        
        # 광고주 분류
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
    
    # 6. 복귀
    d.press("back")
    time.sleep(1)
    d.press("back") # 목록 -> 홈
    time.sleep(2)

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 모니터링 시작...")

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
