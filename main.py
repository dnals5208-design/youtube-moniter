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
KEYWORDS = ["해커스"] 
REPEAT_COUNT = 10 
SCREENSHOT_DIR = "screenshots"
FIXED_AD_ID = "38400000-8cf0-11bd-b23e-10b96e4ef00d" 

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
        header = ["시간", "키워드", "회차", "광고여부", "광고주_구분", "상세_광고주", "광고형태", "제목/텍스트", "앱버전"]
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
                data["광고형태"], data["제목/텍스트"], data["앱버전"]
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
    """최신 앱 팝업 제거"""
    try:
        if d(textContains="Accept").exists: d(textContains="Accept").click()
        if d(textContains="No thanks").exists: d(textContains="No thanks").click()
        if d(textContains="Allow").exists: d(textContains="Allow").click() # 알림 허용
        if d(textContains="better keyboard").exists: d(textContains="No").click()
        if d(text="Skip trial").exists: d(text="Skip trial").click()
        if d(textContains="Try searching").exists: d.click(0.5, 0.2) # 힌트 팝업 닫기
    except: pass

def inject_fixed_ad_id(d):
    print(f"   💉 고정 Advertising ID 주입: {FIXED_AD_ID}")
    d.shell(f"settings put global google_ad_id {FIXED_AD_ID}")
    d.shell("settings put global ad_id_enabled 1")
    d.shell("settings put secure limit_ad_tracking 0")

def check_youtube_version(d):
    try:
        version_output = d.shell("dumpsys package com.google.android.youtube | grep versionName").output.strip()
        print(f"\n   📱 [앱정보] YouTube Version: {version_output}")
        if "=" in version_output: return version_output.split("=")[1]
        return version_output
    except: return "Unknown"

# ==========================================
# [기능] 안전한 검색 버튼 클릭 (수정됨)
# ==========================================
def safe_click_search_button(d):
    # 1. 리소스 ID로 시도 (가장 정확)
    if d(resourceId="com.google.android.youtube:id/menu_item_search").exists:
        d(resourceId="com.google.android.youtube:id/menu_item_search").click()
        return True
    
    # 2. 한글 '검색' (한국어 설정 대비)
    if d(description="검색").exists:
        d(description="검색").click()
        return True
        
    # 3. 영어 'Search'
    if d(description="Search").exists:
        d(description="Search").click()
        return True
        
    # 4. 최후의 수단: 우상단 좌표 클릭
    print("   ⚠️ 검색 버튼 못 찾음 -> 좌표 강제 클릭")
    d.click(0.85, 0.05)
    return True

# ==========================================
# [기능] 인간 행동 모방 (빌드업)
# ==========================================
def human_warmup_routine(d):
    print("\n   🙋‍♂️ [빌드업] 실제 사람인 척 연기 중... (광고 활성화 유도)")
    
    # 0. 팝업 한번 더 청소 (최초 실행 시 방해 요소 제거)
    nuke_popups(d)
    time.sleep(1)

    # 1. 일반적인 인기 키워드 검색
    warmup_keyword = "뉴스"
    print(f"   📺 '{warmup_keyword}' 검색 시도...")
    
    # ★ 수정된 안전 클릭 함수 사용
    safe_click_search_button(d)
    
    time.sleep(2)
    
    # 검색창이 활성화 안 됐을 수 있으니 체크
    if not d(resourceId="com.google.android.youtube:id/search_edit_text").exists:
         safe_click_search_button(d) # 한번 더 클릭
         time.sleep(1)

    d.shell(f"input text '{warmup_keyword}'")
    time.sleep(1)
    d.shell("input keyevent 66") # Enter
    time.sleep(5)
    
    # 2. 영상 시청
    # 화면 중앙 클릭 (영상 진입)
    d.click(0.5, 0.4) 
    print("   👀 영상 시청 중 (15초)...")
    time.sleep(15)
    
    # 3. 홈 복귀 대신 검색 모드로 전환
    print("   🕵️ 이제 진짜 타겟 키워드 검색 준비...")
    # 뒤로가기 대신 바로 검색 버튼을 누름
    if not safe_click_search_button(d):
        d.press("back") # 영상에서 나오고
        time.sleep(1)
        safe_click_search_button(d) # 다시 검색 클릭

    time.sleep(2)
    # 기존 검색어 지우기 (X버튼)
    if d(resourceId="com.google.android.youtube:id/search_clear_button").exists:
        d(resourceId="com.google.android.youtube:id/search_clear_button").click()
    time.sleep(1)

# ==========================================
# [설정] 유튜브 실행 (기록 켜둠!)
# ==========================================
def setup_youtube_persistent(d):
    print("   🧹 유튜브 앱 데이터 초기화...")
    d.shell("pm clear com.google.android.youtube")
    time.sleep(3)
    inject_fixed_ad_id(d)
    
    print("   🔨 유튜브 실행...")
    d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
    time.sleep(12) # 최신 앱은 로딩이 좀 걸림
    nuke_popups(d)
    
    print("   ✅ 기록 누적 모드 ON (설정 변경 안 함)")

def perform_search_and_analyze(d, keyword, worksheet, count, app_ver):
    print(f"\n🔎 [{count}] '{keyword}' 타겟 검색 시작...")
    
    # 검색창 진입 체크
    if not d(resourceId="com.google.android.youtube:id/search_edit_text").exists:
         safe_click_search_button(d)
         time.sleep(2)

    # 기존 텍스트 지우기
    if d(resourceId="com.google.android.youtube:id/search_edit_text").exists:
        if d(resourceId="com.google.android.youtube:id/search_clear_button").exists:
            d(resourceId="com.google.android.youtube:id/search_clear_button").click()
        else:
            d(resourceId="com.google.android.youtube:id/search_edit_text").clear_text()
    
    time.sleep(1)
    print(f"   ⌨️ '{keyword}' 입력...")
    d.shell(f"input text '{keyword}'")
    time.sleep(2)
    
    print("   🚀 검색 실행...")
    d.shell("input keyevent 66") 
    
    print("   ⏳ 광고 로딩 대기 (10초)...")
    time.sleep(10)
    
    # 화면 정리
    d.press("back") # 키보드 내리기
    time.sleep(1)
    d.swipe(0.5, 0.3, 0.5, 0.8, 0.3) # 맨 위로
    time.sleep(2)
    
    screen_text = read_screen_text(d, filename=f"{keyword}_{count}.png")
    
    is_ad = "X"
    ad_corp, ad_detail, ad_type, ad_title = "-", "-", "-", "-"
    
    if any(x in screen_text for x in ["Ad", "Sponsored", "광고", "Promoted"]):
        is_ad = "O"
        if "조회수" in screen_text or "views" in screen_text: ad_type = "영상광고"
        else: ad_type = "배너/검색광고"
        lines = [line for line in screen_text.split('\n') if len(line) > 5]
        for line in lines:
            if "광고" not in line and "Ad" not in line:
                ad_title = line; break
        ad_corp, ad_detail = classify_advertiser(screen_text)
        print(f"   🚨 광고 발견! [{ad_corp}]")
    else:
        print("   ❌ 광고 없음")
        
    data = {
        "시간": datetime.now().strftime('%H:%M:%S'),
        "키워드": keyword, "회차": count, "광고여부": is_ad,
        "광고주_구분": ad_corp, "상세_광고주": ad_detail,
        "광고형태": ad_type, "제목/텍스트": ad_title,
        "앱버전": app_ver
    }
    append_to_sheet(worksheet, data)
    
    # 다음 검색을 위해 뒤로가기
    d.press("back") 

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 모니터링 시작 (Human Simulation Mode)...")
    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        # 1. 버전 체크
        app_ver = check_youtube_version(d)
        
        # 2. 초기화
        setup_youtube_persistent(d)
        
        # 3. 웜업 (안전한 클릭 적용)
        try:
            human_warmup_routine(d)
        except Exception as e:
            print(f"   ⚠️ 웜업 중 오류 발생 (무시하고 본 검색 진행): {e}")

        # 4. 본 검색 시작
        for keyword in KEYWORDS:
            for i in range(1, REPEAT_COUNT + 1):
                if d.app_current()['package'] != "com.google.android.youtube":
                    d.shell("am start -n com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity")
                    time.sleep(5)
                
                nuke_popups(d)
                perform_search_and_analyze(d, keyword, ws, i, app_ver)
                
    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    if not os.path.exists(SCREENSHOT_DIR): os.makedirs(SCREENSHOT_DIR)
    run_android_monitoring()
