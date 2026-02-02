import time
import uiautomator2 as u2
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import sys
import pytesseract # OCR 라이브러리
from PIL import Image # 이미지 처리

# ==========================================
# [설정]
# ==========================================
ADB_ADDR = "emulator-5554" 
KEYWORDS = ["해커스", "토익", "경찰공무원", "소방공무원", "공무원"]
REPEAT_COUNT = 10 

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
        except:
            print(f"   🆕 새 시트('{sheet_name}')를 생성합니다.")
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
# [기능] 네트워크 강제 복구
# ==========================================
def fix_network_settings(d):
    print("🚑 네트워크 설정 강제 수정 중...")
    d.shell("settings put global captive_portal_mode 0")
    d.shell("settings put global private_dns_mode off")
    d.shell("cmd connectivity airplane-mode enable")
    time.sleep(2)
    d.shell("cmd connectivity airplane-mode disable")
    time.sleep(5)
    print("   ✅ 네트워크 패치 완료")

# ==========================================
# [기능] OCR (화면 캡처해서 글자 읽기) - 핵심!
# ==========================================
def read_screen_text(d):
    try:
        # 스크린샷 찍어서 파일로 저장
        d.screenshot("current_screen.png")
        
        # 저장된 이미지를 읽어서 텍스트로 변환 (한글+영어)
        text = pytesseract.image_to_string(Image.open("current_screen.png"), lang='kor+eng')
        
        # 줄바꿈 제거하고 한 줄로 정리
        clean_text = " ".join(text.split())
        return clean_text
    except Exception as e:
        print(f"   ⚠️ OCR 읽기 실패: {e}")
        return ""

# ==========================================
# [기능] 인터넷 연결 확인 (OCR 방식)
# ==========================================
def check_internet_via_browser(d):
    print("🌐 인터넷 연결 확인 중 (OCR 모드)...")
    fix_network_settings(d)
    
    d.app_start("com.android.chrome")
    time.sleep(3)
    d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io"')
    time.sleep(10) 
    
    screen_text = read_screen_text(d)
    
    if "No internet" in screen_text or "ERR_" in screen_text:
         print("   ❌ 인터넷 연결 실패 (크롬 에러 화면)")
         return False
    
    print(f"   ✅ 인터넷 연결 확인됨 (화면 텍스트 일부: {screen_text[:30]}...)")
    return True

# ==========================================
# [기능] 유튜브 제어
# ==========================================
def handle_popups_and_incognito(d):
    print("   🔨 초기 설정 진행 중...")
    # 좌표로 팝업 닫기 시도 (중앙 하단, 중앙 등)
    d.click(0.5, 0.9) # Got it 위치 추정
    time.sleep(1)
    
    print("   🕵️ 시크릿 모드 진입...")
    d.click(0.92, 0.05) # 프로필
    time.sleep(2)
    
    # OCR로 메뉴 찾기 (좌표 클릭 시도)
    text = read_screen_text(d)
    if "Secret" in text or "시크릿" in text or "Incognito" in text:
        # 메뉴가 떴으면 적당한 위치 클릭 (목록 중 하나겠거니 하고 좌표 클릭)
        # 보통 시크릿 모드는 상단부에 있음
        d.click(0.5, 0.3) 
    else:
        # 안 떴으면 그냥 프로필 다시 누르고 좌표로 찍음
        d.click(0.92, 0.05)
        time.sleep(1)
        d.click(0.5, 0.35) # 대략적인 시크릿모드 메뉴 위치
    
    time.sleep(4)
    d.click(0.5, 0.9) # Got it 닫기
    print("   ✅ 설정 완료 (좌표 기반)")

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 에뮬레이터 연결 (Android 13 + OCR)...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        check_internet_via_browser(d)
        
        print("   -> 🔴 YouTube APP 실행")
        d.app_stop("com.google.android.youtube")
        d.app_start("com.google.android.youtube")
        time.sleep(10) 
        
        handle_popups_and_incognito(d)

        for keyword in KEYWORDS:
            print(f"\n🔎 [{keyword}] 검색 시작")
            
            for i in range(1, REPEAT_COUNT + 1):
                sys.stdout.flush()
                print(f"   [{i}/{REPEAT_COUNT}] 진행 중...", end=" ")
                
                # 1. 돋보기 클릭 (좌표)
                d.click(0.9, 0.05) 
                time.sleep(2)
                
                # 2. 검색어 입력
                d.send_keys(keyword)
                d.press("enter")
                
                # 3. 로딩 대기
                time.sleep(10)
                d.swipe(500, 1500, 500, 500, 0.3) 
                time.sleep(3)
                
                # 4. ★ OCR로 화면 분석
                screen_text = read_screen_text(d)
                
                is_ad = "X"
                ad_text = "-"
                
                # 텍스트에서 광고 키워드 찾기
                if "광고" in screen_text or "Ad" in screen_text or "Sponsored" in screen_text:
                    is_ad = "O"
                    ad_text = "광고 발견 (OCR 인식)"
                    
                    # 광고주 찾기
                    for k in ["해커스", "에듀윌", "공단기", "메가", "경단기", "소방", "야나두", "시원스쿨", "YBM"]:
                        if k in screen_text:
                            ad_text = f"{k} 광고"
                            break
                    print(f"🚨 발견! ({ad_text})")
                else:
                    # 디버깅용: 읽은 글자 앞부분만 출력
                    print(f"❌ 없음 (OCR 인식내용: {screen_text[:40]}...)")
                
                result_data = {
                    "날짜": datetime.now().strftime('%Y-%m-%d'),
                    "시간": datetime.now().strftime('%H:%M:%S'),
                    "키워드": keyword,
                    "회차": i,
                    "광고여부": is_ad, 
                    "비고": f"{ad_text}"
                }
                append_to_sheet(ws, result_data)
                
                # 5. 초기화 (뒤로가기)
                d.press("back")
                time.sleep(1)
                d.press("back")
                time.sleep(2)
                # 검색창 남아있으면 한번 더
                d.press("back") 

    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    run_android_monitoring()
