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
# [기능] IP 확인 (팝업 제거 강화)
# ==========================================
def check_ip_and_setup(d):
    print("🌐 인터넷 및 IP 위치 확인 중...")
    
    # 네트워크 패치
    d.shell("settings put global captive_portal_mode 0")
    d.shell("settings put global private_dns_mode off")
    
    # 크롬 실행
    d.app_start("com.android.chrome")
    time.sleep(5)
    
    # 1. Welcome 화면 넘기기 (Accept)
    d.click(0.5, 0.9) 
    time.sleep(2)
    
    # 2. 동기화 설정 넘기기 (No Thanks) - 좌측 하단
    d.click(0.2, 0.9) 
    time.sleep(3)

    # ★ 3. 알림 권한 팝업 넘기기 (No Thanks) - 한번 더 클릭
    # (이미지 1번 문제 해결)
    if d(text="No thanks").exists:
        d(text="No thanks").click()
    else:
        # 혹시 텍스트 못 찾으면 좌표로 (좌측 하단)
        d.click(0.2, 0.9)
    time.sleep(2)

    # IP 확인 사이트 접속
    d.shell('am start -a android.intent.action.VIEW -d "https://ipinfo.io/json"')
    time.sleep(8) 
    
    # 스크린샷 저장
    screen_text = read_screen_text(d, filename="ip_check.png")
    
    if "KR" in screen_text or "Korea" in screen_text or "South Korea" in screen_text:
        print(f"   ✅ 한국 IP 확인됨! (내용: {screen_text[:30]}...)")
    else:
        print(f"   ⚠️ 한국 IP 아닐 수 있음 (내용: {screen_text[:30]}...)")

# ==========================================
# [기능] 유튜브 실행
# ==========================================
def setup_youtube(d):
    print("   🔨 유튜브 어플 실행...")
    d.app_stop("com.google.android.youtube")
    d.app_start("com.google.android.youtube")
    time.sleep(8)

    # 팝업 닫기 (Got it 등)
    d.click(0.5, 0.9) 
    time.sleep(1)

    # 시크릿 모드
    print("   🕵️ 시크릿 모드 진입...")
    d.click(0.92, 0.05) 
    time.sleep(2)
    
    # 한국어 설정을 했으므로 '시크릿 모드 사용' 한글을 찾을 수도 있음
    text = read_screen_text(d)
    if "Secret" in text or "시크릿" in text or "Incognito" in text:
        d.click(0.5, 0.3) 
    else:
        d.click(0.92, 0.05)
        time.sleep(1)
        d.click(0.5, 0.35) 
    
    time.sleep(4)
    d.click(0.5, 0.9)

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 에뮬레이터 연결...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        check_ip_and_setup(d)
        setup_youtube(d)

        for keyword in KEYWORDS:
            print(f"\n🔎 [{keyword}] 검색 시작")
            
            for i in range(1, REPEAT_COUNT + 1):
                sys.stdout.flush()
                print(f"   [{i}/{REPEAT_COUNT}] 진행 중...", end=" ")
                
                # 딥링크 검색
                cmd = f'am start -a android.intent.action.VIEW -d "https://www.youtube.com/results?search_query={keyword}" -p com.google.android.youtube'
                d.shell(cmd)
                
                # 로딩 대기
                time.sleep(8)
                
                # ★ 중요 수정: 스크롤하기 전에 먼저 찍는다! (최상단 광고 확인용)
                screen_text_top = read_screen_text(d, filename=f"{keyword}_{i}_top.png")
                
                # 그 다음 스크롤 (아래쪽 확인용)
                d.swipe(500, 1500, 500, 500, 0.3) 
                time.sleep(2)
                
                # (옵션) 스크롤 후도 찍고 싶으면 여기서 한번 더 찍어도 됨
                # screen_text_bottom = read_screen_text(d, filename=f"{keyword}_{i}_bottom.png")
                # 일단은 위쪽 텍스트(screen_text_top)를 기준으로 판단
                
                screen_text = screen_text_top
                
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
