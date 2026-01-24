import time
import pandas as pd
from playwright.sync_api import sync_playwright
import os

# ==========================================
# [설정] 키워드 리스트
# ==========================================
KEYWORDS = [
    "해커스", "토익", "경찰공무원", 
    "소방공무원", "공무원", "텝스", 
    "토익스피킹", "공인중개사", "토스"
]

TARGET_SUCCESS_COUNT = 10 
MAX_FAILURE_LIMIT = 30
WAIT_TIME = 2.0 # 서버는 느릴 수 있어서 조금 넉넉하게

# ==========================================
# [설정] 광고주 분류 함수
# ==========================================
def classify_advertiser(text):
    text = text.replace(" ", "")
    if "해커스" not in text: return "타사", text
    if "공무원" in text: return "해커스공무원", "해커스"
    if "경찰" in text: return "해커스경찰", "해커스"
    if "소방" in text: return "해커스소방", "해커스"
    if "자격증" in text or "기사" in text: return "해커스자격증", "해커스"
    if "공인중개사" in text or "주택관리사" in text: return "해커스공인중개사", "해커스"
    if "금융" in text: return "해커스금융", "해커스"
    if "잡" in text or "취업" in text or "면접" in text: return "해커스잡", "해커스"
    if "편입" in text: return "해커스편입", "해커스"
    if "어학" in text or "토익" in text or "텝스" in text or "토스" in text or "오픽" in text: return "해커스어학", "해커스"
    return "해커스(기타)", "해커스"

# ==========================================
# [핵심] 크롤링 실행 (Playwright)
# ==========================================
def run_crawling():
    results = []
    
    with sync_playwright() as p:
        # 1. PC 모드
        print("🖥️ [PC] 모드 시작...")
        browser_pc = p.chromium.launch(headless=True) # ★ True: 화면 없이 실행
        context_pc = browser_pc.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page_pc = context_pc.new_page()
        
        for keyword in KEYWORDS:
            print(f" >> [PC] {keyword}")
            success = 0; fails = 0
            while success < TARGET_SUCCESS_COUNT:
                if fails >= MAX_FAILURE_LIMIT:
                    remaining = TARGET_SUCCESS_COUNT - success
                    for _ in range(remaining):
                        success += 1
                        results.append({"디바이스": "PC", "회차": success, "키워드": keyword, "광고여부": "X", "광고주_구분": "미노출", "상세_광고주": "-", "광고형태": "-", "영상제목/배너카피": "-"})
                    break
                try:
                    page_pc.goto(f"https://www.youtube.com/results?search_query={keyword}", wait_until="domcontentloaded")
                    time.sleep(WAIT_TIME)
                    
                    found_ad = None
                    # 광고 태그 찾기
                    ads = page_pc.locator("ytd-promoted-sparkles-web-renderer, ytd-ad-slot-renderer, ytd-video-renderer").all()
                    for ad in ads:
                        if "광고" in ad.inner_text() or "Ad" in ad.inner_text():
                            found_ad = ad; break
                    
                    if found_ad:
                        raw = found_ad.inner_text().split('\n')
                        title = raw[1] if len(raw) > 1 else raw[0]
                        advertiser = "알수없음"
                        for r in raw:
                            if len(r) < 40 and "http" not in r and r != title: advertiser = r; break
                        
                        biz, comp = classify_advertiser(advertiser + " " + title)
                        is_video = "조회수" in found_ad.inner_text()
                        results.append({"디바이스": "PC", "회차": success+1, "키워드": keyword, "광고여부": "O", "광고주_구분": comp, "상세_광고주": biz, "광고형태": "영상" if is_video else "배너", "영상제목/배너카피": title})
                        success += 1
                    else:
                        if keyword == "공무원": # 공무원은 광고 없어도 기록
                             results.append({"디바이스": "PC", "회차": success+1, "키워드": keyword, "광고여부": "X", "광고주_구분": "-", "상세_광고주": "-", "광고형태": "-", "영상제목/배너카피": "-"})
                             success += 1
                        else: fails += 1
                except: fails += 1
        browser_pc.close()

        # 2. Mobile 모드 (아이폰 13 Pro 에뮬레이션)
        print("📱 [Mobile] 모드 시작...")
        iphone_13 = p.devices['iPhone 13 Pro'] # ★ 서버에서 제공하는 완벽한 기기 정보
        
        browser_mo = p.chromium.launch(headless=True) # ★ True: 화면 없이 실행
        context_mo = browser_mo.new_context(**iphone_13, locale='ko-KR')
        page_mo = context_mo.new_page()

        for keyword in KEYWORDS:
            print(f" >> [MO] {keyword}")
            success = 0; fails = 0
            while success < TARGET_SUCCESS_COUNT:
                if fails >= MAX_FAILURE_LIMIT:
                    remaining = TARGET_SUCCESS_COUNT - success
                    for _ in range(remaining):
                        success += 1
                        results.append({"디바이스": "Mobile", "회차": success, "키워드": keyword, "광고여부": "X", "광고주_구분": "미노출", "상세_광고주": "-", "광고형태": "-", "영상제목/배너카피": "-"})
                    break
                try:
                    page_mo.goto(f"https://m.youtube.com/results?search_query={keyword}", wait_until="domcontentloaded")
                    time.sleep(WAIT_TIME)
                    
                    found_ad = None
                    ads = page_mo.locator("ytm-promoted-sparkles-web-renderer, ytm-item-section-renderer, ytm-video-with-context-renderer").all()
                    for ad in ads:
                        if "광고" in ad.inner_text() or "Ad" in ad.inner_text():
                            found_ad = ad; break
                            
                    if found_ad:
                        raw = found_ad.inner_text().split('\n')
                        title = raw[1] if len(raw) > 1 else raw[0]
                        advertiser = "알수없음"
                        for r in raw:
                            if len(r) < 40 and "http" not in r and r != title: advertiser = r; break
                            
                        biz, comp = classify_advertiser(advertiser + " " + title)
                        is_video = "조회수" in found_ad.inner_text()
                        results.append({"디바이스": "Mobile", "회차": success+1, "키워드": keyword, "광고여부": "O", "광고주_구분": comp, "상세_광고주": biz, "광고형태": "영상" if is_video else "배너", "영상제목/배너카피": title})
                        success += 1
                    else:
                        if keyword == "공무원":
                             results.append({"디바이스": "Mobile", "회차": success+1, "키워드": keyword, "광고여부": "X", "광고주_구분": "-", "상세_광고주": "-", "광고형태": "-", "영상제목/배너카피": "-"})
                             success += 1
                        else: fails += 1
                except: fails += 1
        browser_mo.close()

    return results

if __name__ == "__main__":
    data = run_crawling()
    if data:
        df = pd.DataFrame(data)
        # 엑셀 파일명 (서버 시간 기준)
        filename = f"Youtube_Monitor_Result.xlsx"
        df.to_excel(filename, index=False)
        print("✅ 완료")