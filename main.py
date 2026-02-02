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
# [기능] OCR (화면 읽기)
# ==========================================
def read_screen_text(d):
    try:
        d.screenshot("current_screen.png")
        text = pytesseract.image_to_string(Image.open("current_screen.png"), lang='kor+eng')
        clean_text = " ".join(text.split())
        return clean_text
    except Exception as e:
        print(f"   ⚠️ OCR 읽기 실패: {e}")
        return ""

# ==========================================
# [기능] 인터넷/IP 확인 (IP 위치 출력 추가)
# ==========================================
def check_internet_via_browser(d):
    print("🌐 인터넷 및 IP 위치 확인 중...")
    fix_network_settings(d)
    
    d.app_start("com.android.chrome")
    time.sleep(3)
    # ipinfo.io로 접속해서 국가코드 확인
    d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io/json"')
    time.sleep(8) 
    
    screen_text = read_screen_text(d)
    
    if "No internet" in screen_text or "ERR_" in screen_text:
         print("   ❌ 인터넷 연결 실패")
         return False
    
    # 국가 코드 확인
    if "KR" in screen_text or "Korea" in screen_text:
        print(f"   ✅ 한국 IP 확인됨! (OCR 내용: {screen_text[:30]}...)")
    else:
        print(f"   ⚠️ 한국 IP 아닐 수 있음 (OCR 내용: {screen_text[:30]}...)")
        
    return True

# ==========================================
# [기능] 유튜브 실행 및 설정
# ==========================================
def setup_youtube(d):
    print("   🔨 유튜브 초기 설정...")
    
    # 딥링크로 일단 유튜브를 한 번 켬
    d.shell('am start -a android.intent.action.VIEW -d "https://www.youtube.com" -p com.google.android.youtube')
    time.sleep(10)

    # 팝업 대충 닫기 (좌표)
    d.click(0.5, 0.9) # Got it / Skip
    time.sleep(1)
    d.click(0.5, 0.8) # No thanks
    time.sleep(1)

    print("   🕵️ 시크릿 모드 진입 시도...")
    d.click(0.92, 0.05) # 프로필
    time.sleep(2)
    
    # OCR로 메뉴 확인
    text = read_screen_text(d)
    if "Secret" in text or "시크릿" in text or "Incognito" in text:
        d.click(0.5, 0.3) # 대략적 위치
    else:
        d.click(0.92, 0.05)
        time.sleep(1)
        d.click(0.5, 0.35) 
    
    time.sleep(4)
    d.click(0.5, 0.9) # Got it
    print("   ✅ 설정 완료")

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 에뮬레이터 연결...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        # 1. 인터넷 & IP 확인
        check_internet_via_browser(d)
        
        # 2. 유튜브 켜고 시크릿 모드
        setup_youtube(d)

        for keyword in KEYWORDS:
            print(f"\n🔎 [{keyword}] 검색 시작 (딥링크 방식)")
            
            for i in range(1, REPEAT_COUNT + 1):
                sys.stdout.flush()
                print(f"   [{i}/{REPEAT_COUNT}] 진행 중...", end=" ")
                
                # ★ 핵심 변경: 딥링크로 검색 결과 페이지 강제 이동
                # 앱이 꺼져있든 켜져있든 상관없이 바로 검색 결과로 점프함
                # 뒤로가기 누를 필요 없음
                cmd = f'am start -a android.intent.action.VIEW -d "https://www.youtube.com/results?search_query={keyword}" -p com.google.android.youtube'
                d.shell(cmd)
                
                # 로딩 대기
                time.sleep(10)
                
                # 스크롤 (광고 로딩 유도)
                d.swipe(500, 1500, 500, 500, 0.3) 
                time.sleep(3)
                
                # OCR로 화면 분석
                screen_text = read_screen_text(d)
                
                is_ad = "X"
                ad_text = "-"
                
                # 바탕화면으로 튕겼는지 확인 (Settings, Clock 등이 보이면 튕긴 것)
                if "Settings" in screen_text and "Clock" in screen_text:
                     print("   ⚠️ 바탕화면으로 튕김 -> 다음 루프에서 재진입")
                     # 재진입을 위해 아무것도 안 하고 넘어감 (다음 딥링크가 해결해줌)
                
                elif "광고" in screen_text or "Ad" in screen_text or "Sponsored" in screen_text:
                    is_ad = "O"
                    ad_text = "광고 발견"
                    for k in ["해커스", "에듀윌", "공단기", "메가", "경단기", "소방", "야나두", "시원스쿨", "YBM", "Hackers"]:
                        if k in screen_text:
                            ad_text = f"{k} 광고"
                            break
                    print(f"🚨 발견! ({ad_text})")
                else:
                    print(f"❌ 없음 (인식: {screen_text[:30]}...)")
                
                result_data = {
                    "날짜": datetime.now().strftime('%Y-%m-%d'),
                    "시간": datetime.now().strftime('%H:%M:%S'),
                    "키워드": keyword,
                    "회차": i,
                    "광고여부": is_ad, 
                    "비고": f"{ad_text}"
                }
                append_to_sheet(ws, result_data)
                
                # 뒤로가기 로직 삭제함 (딥링크가 알아서 처리)
                time.sleep(1)

    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    run_android_monitoring()
