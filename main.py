import time
import uiautomator2 as u2
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import sys
import re # 정규표현식 추가 (화면 분석 강화)

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
            print(f"   ♻️ 기존 시트('{sheet_name}') 발견! 초기화합니다.")
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
# [기능] 유튜브 제어
# ==========================================
def handle_popups_and_incognito(d):
    print("   🔨 초기 설정 진행 중...")
    
    # 팝업 닫기
    for _ in range(3):
        if d(text="Don't allow").exists: d(text="Don't allow").click()
        if d(text="허용 안함").exists: d(text="허용 안함").click()
        if d(text="Got it").exists: d(text="Got it").click()
        time.sleep(1)

    # 시크릿 모드 진입
    print("   🕵️ 시크릿 모드 진입...")
    d.click(0.92, 0.05) # 우측 상단 프로필
    time.sleep(2)
    
    # 메뉴 찾기 (text와 content-desc 모두 확인)
    if d(text="Turn on Incognito").exists:
        d(text="Turn on Incognito").click()
    elif d(text="시크릿 모드 사용").exists:
        d(text="시크릿 모드 사용").click()
    elif d(resourceId="com.google.android.youtube:id/incognito_item").exists:
        d(resourceId="com.google.android.youtube:id/incognito_item").click()
    else:
        # 메뉴가 안 떴으면 한 번 더 시도
        d.click(0.92, 0.05)
        time.sleep(1)
        if d(resourceId="com.google.android.youtube:id/incognito_item").exists:
             d(resourceId="com.google.android.youtube:id/incognito_item").click()
    
    time.sleep(4)
    if d(text="Got it").exists: d(text="Got it").click()
    print("   ✅ 설정 완료")

def run_android_monitoring():
    ws = get_worksheet()
    print(f"📱 [MO] 에뮬레이터 연결 (Android 13)...")

    try:
        os.system("adb wait-for-device")
        d = u2.connect(ADB_ADDR)
        
        # 앱 실행
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
                
                # 1. 검색창 진입 (돋보기 클릭)
                # (뒤로가기로 초기화했으므로 항상 홈 화면 상태라고 가정)
                if not d(resourceId="com.google.android.youtube:id/search_edit_text").exists:
                    d.click(0.9, 0.05) # 우측 상단 돋보기 위치 클릭
                    time.sleep(2)
                
                # 2. 검색어 입력
                d.send_keys(keyword)
                d.press("enter")
                
                # 3. 로딩 대기
                time.sleep(10)
                
                # 4. 스크롤 (광고 로딩 유도)
                d.swipe(500, 1500, 500, 500, 0.3) 
                time.sleep(2)
                
                # 5. 화면 분석 (강화된 로직)
                is_ad = "X"
                ad_text = "-"
                
                try:
                    xml = d.dump_hierarchy()
                    
                    # '광고', 'Ad', 'Sponsored' 키워드 찾기 (text 및 content-desc 모두 검색)
                    # 정규표현식으로 text="..." 또는 content-desc="..." 안의 내용을 추출
                    texts_found = re.findall(r'(?:text|content-desc)="([^"]*)"', xml)
                    
                    # 광고 배지 확인
                    ad_badge_found = False
                    for t in texts_found:
                        if t in ["광고", "Ad", "Sponsored", "이 광고", "앱 설치"]:
                            ad_badge_found = True
                            break
                    
                    if ad_badge_found:
                        is_ad = "O"
                        # 광고주 찾기 (해커스 등 키워드 포함된 텍스트 탐색)
                        for t in texts_found:
                            # 광고주 텍스트 조건: 길이가 적당하고, '광고' 단어가 아니고, 타임스탬프가 아님
                            if len(t) > 1 and "광고" not in t and "분 전" not in t and "조회수" not in t:
                                 if any(k in t for k in ["해커스", "에듀윌", "공단기", "메가", "경단기", "소방", "야나두", "시원스쿨", "YBM"]):
                                     ad_text = t
                                     break
                        if ad_text == "-": ad_text = "광고발견(상세미상)"
                        print(f"🚨 발견! ({ad_text})")
                    else:
                        # 디버깅: 화면에 보이는 주요 텍스트 5개만 출력해봄
                        summary = ", ".join([t for t in texts_found if len(t) > 3][:5])
                        print(f"❌ 없음 (화면: {summary}...)")

                except Exception as xml_e:
                    print(f"⚠️ 화면 읽기 실패: {xml_e}")
                
                # 6. 결과 저장
                result_data = {
                    "날짜": datetime.now().strftime('%Y-%m-%d'),
                    "시간": datetime.now().strftime('%H:%M:%S'),
                    "키워드": keyword,
                    "회차": i,
                    "광고여부": is_ad, 
                    "비고": f"{ad_text}"
                }
                append_to_sheet(ws, result_data)
                
                # 7. ★ 중요: 초기화 (뒤로가기 전략)
                # clear_text() 대신 뒤로가기를 연타하여 검색 모드를 빠져나감
                d.press("back") # 키보드 내리기 / 검색창 닫기
                time.sleep(1)
                d.press("back") # 검색 결과창 나가기 (홈으로 복귀)
                time.sleep(2)
                
                # 만약 홈으로 안 갔을까봐 한 번 더 체크 (검색창이 여전히 있으면 뒤로가기)
                if d(resourceId="com.google.android.youtube:id/search_edit_text").exists:
                     d.press("back")
                     time.sleep(1)

    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    run_android_monitoring()
