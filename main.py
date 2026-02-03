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
# [기능] 구글 시트 연결 (초기화)
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
            print(f"   ♻️ 기존 시트('{sheet_name}') 발견! 내용을 초기화합니다.")
            worksheet.clear() 
            worksheet.append_row(header)
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
# [기능] OCR 및 스크린샷
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
# [기능] IP 확인 (명령어로 직접 확인 - 크롬 무시)
# ==========================================
def check_ip_silent(d):
    print("🌐 IP 위치 확인 중 (ADB 명령어)...")
    
    # 1. 네트워크 패치
    d.shell("settings put global captive_portal_mode 0")
    d.shell("settings put global private_dns_mode off")
    
    # 2. Curl 명령어로 IP 정보 직접 가져오기 (화면 X)
    try:
        # 15초 타임아웃
        output = d.shell("curl -s --connect-timeout 15 https://ipinfo.io/json").output
        
        print(f"   📄 IP 응답 데이터: {output}")
        
        if "KR" in output or "Korea" in output:
            print("   ✅ [성공] 한국 IP 확인됨! (Tunneling 정상)")
        elif "US" in output:
             print("   ⚠️ 미국 IP 잡힘 (프록시 무시됨)")
        elif "Could not resolve" in output or "curl: (6)" in output:
             print("   ❌ 인터넷 연결 안 됨 (터널 막힘)")
        else:
            print("   ⚠️ IP 정보 확인 불가 (응답값 이상)")
            
    except Exception as e:
        print(f"   ❌ IP 확인 명령어 실패: {e}")

# ==========================================
# [기능] 크롬 'Welcome' 화면 스킵 (스마트 클릭)
# ==========================================
def skip_chrome_welcome(d):
    print("   🔨 크롬 설정 건너뛰기...")
    d.app_start("com.android.chrome")
    time.sleep(3)
    
    # "Accept & continue" 또는 "동의 및 계속" 버튼 텍스트로 찾기
    if d(text="Accept & continue").exists:
        d(text="Accept & continue").click()
    elif d(text="동의 및 계속").exists:
        d(text="동의 및 계속").click()
    else:
        # 못 찾으면 기존 좌표 클릭
        d.click(0.5, 0.9)
    time.sleep(2)
    
    # "No thanks" 또는 "사용 안함"
    if d(text="No thanks").exists:
        d(text="No thanks").click()
    elif d(text="사용 안함").exists:
        d(text="사용 안함").click()
    else:
        d.click(0.25, 0.9)
    time.sleep(1)

# ==========================================
# [기능] 유튜브 실행
# ==========================================
def setup_youtube(d):
    print("   🔨 유튜브 어플 실행...")
    d.app_stop("com.google.android.youtube")
    d.app_start("com.google.android.youtube")
    time.sleep(8)
    
    # 팝업 닫기
    d.click(0.5, 0.9) 

    print("   🕵️ 시크릿 모드 진입...")
    d.click(0.92, 0.05) 
    time.sleep(2)
    
    text = read_screen_text(d)
    if "Secret" in text or "시크릿" in text:
        d.click(0.5, 0.3) 
    else:
        d.click(0.92, 0.05)
        time.sleep(1)
        d.click(0.5, 0.35) 
    
    time.sleep(4)
    d.click(0.5, 0.9) # Got it

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 에뮬레이터 연결...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        # 1. 화면 없이 IP 체크 (가장 정확함)
        check_ip_silent(d)
        
        # 2. 크롬 설정 스킵 (혹시 나중에 필요할까봐)
        skip_chrome_welcome(d)
        
        # 3. 유튜브 실행
        setup_youtube(d)

        for keyword in KEYWORDS:
            print(f"\n🔎 [{keyword}] 검색 시작")
            
            for i in range(1, REPEAT_COUNT + 1):
                sys.stdout.flush()
                print(f"   [{i}/{REPEAT_COUNT}] 진행 중...", end=" ")
                
                cmd = f'am start -a android.intent.action.VIEW -d "https://www.youtube.com/results?search_query={keyword}" -p com.google.android.youtube'
                d.shell(cmd)
                
                time.sleep(10)
                
                # 상단 캡처
                screen_text = read_screen_text(d, filename=f"{keyword}_{i}_top.png")
                
                d.swipe(500, 1500, 500, 500, 0.3) 
                time.sleep(2)
                
                is_ad = "X"
                ad_text = "-"
                
                if "광고" in screen_text or "Ad" in screen_text or "Sponsored" in screen_text:
                    is_ad = "O"
                    ad_text = "광고 발견"
                    for k in ["해커스", "에듀윌", "공단기", "메가", "경단기", "소방", "야나두", "시원스쿨", "YBM", "Hackers"]:
                        if k in screen_text:
                            ad_text = f"{k} 광고"
                            break
                    print(f"🚨 발견! ({ad_text})")
                else:
                    print(f"❌ 없음 (인식: {screen_text[:20]}...)")
                
                result_data = {
                    "날짜": datetime.now().strftime('%Y-%m-%d'),
                    "시간": datetime.now().strftime('%H:%M:%S'),
                    "키워드": keyword,
                    "회차": i,
                    "광고여부": is_ad, 
                    "비고": f"{ad_text}"
                }
                append_to_sheet(ws, result_data)
                
    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR)
    run_android_monitoring()
