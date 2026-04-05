import os
import datetime
import sys
import time
import re
from notion_client import Client
import google.generativeai as genai
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경 변수 필수 체크
required_env_vars = ["NOTION_TOKEN", "NOTION_DATABASE_ID", "GEMINI_API_KEY"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]

if missing_vars:
    print(f"❌ 오류: 다음 환경 변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
    sys.exit(1)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

notion = Client(auth=os.getenv("NOTION_TOKEN"))
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# 블로그별 설정 및 프롬프트 강화
COMMON_FORMAT = """
출력 형식:
# [제목]
키워드: [쉼표로 구분된 키워드 3-5개]
참고링크: [관련된 신뢰할 수 있는 웹사이트 URL 하나]
이미지: [주제와 어울리는 Unsplash 이미지 URL 예: https://images.unsplash.com/photo-...]
---
[본문 내용]

주의사항:
1. 본문 내용은 반드시 한국어 기준 공백 포함 3,000자 이상의 매우 상세하고 풍부한 분량으로 작성해줘.
2. 전문적이고 신뢰감 있는 문체를 사용해줘.
3. 소제목을 활용하여 가독성을 높여줘.
4. 모든 블로그 글에는 반드시 주제와 어울리는 고해상도 Unsplash 이미지 URL을 '이미지:' 항목에 포함해줘.
"""

BLOG_TYPES = {
    "네이버(금융)": {
        "prompt": "금융 전문가로서 최근 금리 변화, 환율 변동, 주식 시장 트렌드, 또는 새로운 금융 상품 중 하나를 선정해 일반인도 이해하기 쉬우면서도 깊이 있는 심층 분석글을 작성해줘." + COMMON_FORMAT,
        "tags": "금융, 재테크, 경제"
    },
    "티스토리(행복한 세상)": {
        "prompt": f"오늘은 {datetime.datetime.now().strftime('%Y-%m-%d')}입니다. 구독자들에게 실질적으로 도움이 되는 최신 생활 꿀팁, 복지 혜택, 정부 정책(지원금, 주거 지원 등)을 분석하여 누구나 쉽게 사용법을 이해할 수 있도록 '가이드형' 콘텐츠를 작성해줘. 정책의 배경부터 신청 방법, 유의사항까지 아주 상세하게 포함해줘." + COMMON_FORMAT,
        "tags": "정부지원금, 생활정보, 꿀팁"
    },
    "티스토리(매일 비평)": {
        "prompt": "오늘의 주요 사회, 문화, 또는 정치 이슈 중 하나를 선정해 다각도로 분석하고 날카로운 통찰을 담은 비평글을 작성해줘. 독자들이 생각할 거리를 던져주는 깊이 있는 논조를 유지해줘." + COMMON_FORMAT,
        "tags": "뉴스분석, 시사트렌드, 사회비평"
    }
}

def generate_content_with_retry(blog_name, prompt, max_retries=3):
    # 기존 모델로 원복
    model = genai.GenerativeModel('gemini-flash-latest')
    
    for attempt in range(max_retries):
        try:
            print(f"[{blog_name}] 글 생성 중... (시도 {attempt + 1}/{max_retries})")
            response = model.generate_content(prompt)
            text = response.text
            
            if not text:
                raise ValueError("API 응답에 텍스트가 없습니다.")
            
            # 파싱 로직
            title_match = re.search(r'#\s*(.*)', text)
            title = title_match.group(1).strip() if title_match else "제목 없음"
            
            keywords_match = re.search(r'키워드:\s*(.*)', text)
            keywords = keywords_match.group(1).strip() if keywords_match else ""
            
            ref_link_match = re.search(r'참고링크:\s*(.*)', text)
            ref_link = ref_link_match.group(1).strip() if ref_link_match else ""
            
            img_url_match = re.search(r'이미지:\s*(.*)', text)
            img_url = img_url_match.group(1).strip() if img_url_match else ""
            
            # 본문 추출 (--- 이후 또는 메타데이터 이후)
            content = text.split('---')[-1].strip() if '---' in text else text
            
            # 3000자 미만일 경우 경고 메시지 출력 (재시도는 하지 않음 - 모델 특성상)
            if len(content) < 3000:
                print(f"⚠️ 경고: 생성된 내용이 {len(content)}자로 3000자 미만입니다.")
            
            return {
                "title": title,
                "keywords": keywords,
                "ref_link": ref_link,
                "img_url": img_url,
                "content": content
            }
            
        except Exception as e:
            print(f"오류 발생: {e}")
            if "429" in str(e):
                time.sleep((attempt + 1) * 60)
            else:
                time.sleep(5)
                
    raise Exception("글 생성 실패")

def send_to_notion(blog_name, data):
    properties = {
        "글 제목": {"title": [{"text": {"content": data["title"]}}]},
        "블로그 명": {"select": {"name": blog_name}},
        "작성일": {"date": {"start": datetime.datetime.now().isoformat()}},
        "진행사항": {"select": {"name": "대기중"}},
        "주요 키워드": {"rich_text": [{"text": {"content": data["keywords"]}}]},
    }
    
    # URL 형식 검증 후 추가
    if data["ref_link"].startswith("http"):
        properties["참고링크"] = {"url": data["ref_link"]}
    
    # 이미지 파일 (외부 URL 방식) - 대표 이미지
    if data["img_url"].startswith("http"):
        properties["이미지 파일"] = {
            "files": [{"name": "MainImage", "type": "external", "external": {"url": data["img_url"]}}]
        }

    # 본문 내용을 Notion 블록 제한(2000자)에 맞춰 분할
    content_blocks = []
    
    # 이미지 블록 추가 (본문 상단)
    if data["img_url"].startswith("http"):
        content_blocks.append({
            "object": "block",
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": data["img_url"]}
            }
        })

    # 텍스트 블록 분할 추가
    content = data["content"]
    for i in range(0, len(content), 2000):
        chunk = content[i:i+2000]
        content_blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]}
        })

    notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties=properties,
        children=content_blocks
    )

def main():
    for blog_name, config in BLOG_TYPES.items():
        try:
            data = generate_content_with_retry(blog_name, config["prompt"])
            send_to_notion(blog_name, data)
            print(f"✅ {blog_name} 저장 완료")
            time.sleep(60) 
        except Exception as e:
            print(f"❌ {blog_name} 최종 실패: {e}")

if __name__ == '__main__':
    main()
