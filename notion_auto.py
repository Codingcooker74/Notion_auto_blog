import os
import datetime
import sys
from notion_client import Client
from google import genai
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경 변수 필수 체크
required_env_vars = ["NOTION_TOKEN", "NOTION_DATABASE_ID", "GEMINI_API_KEY"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]

if missing_vars:
    print(f"❌ 오류: 다음 환경 변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
    print("'.env' 파일을 확인하거나 시스템 환경 변수를 설정해주세요.")
    sys.exit(1)

notion = Client(auth=os.getenv("NOTION_TOKEN"))
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 블로그별 설정
BLOG_TYPES = {
    "네이버(금융)": {
        "prompt": "금융 전문가로서 최근 금리 변화나 주식 시장 트렌드 중 하나를 선정해 심층 분석글을 작성해줘. 독자들에게 실질적인 투자 팁을 제공하는 전문적인 톤앤매너를 유지해줘.대표하는 이미지를 포함하고, 제목은 #으로 시작하는 형식으로 작성해줘.",
        "tags": "금융, 재테크, 경제"
    },
    "티스토리(행복한 세상)": {
        "prompt": f"오늘은 {datetime.datetime.now().strftime('%Y-%m-%d')}입니다. 지금으로부터 2주 뒤에 마감되거나 시작되는 정부 지원금, 복지 혜택, 혹은 중요한 국가적 일정을 검색해서 정리해줘. 미리 준비해야 할 서류나 주의사항을 친절하게 안내하는 블로그 글을 써줘. 대표하는 이미지를 포함해줘",
        "tags": "정부지원금, 생활정보, 일정관리"
    },
    "티스토리(매일 비평)": {
        "prompt": "오늘 가장 뜨거운 사회/정치 뉴스 중 하나를 선정해줘. 전문 뉴스 앵커가 스튜디오에서 분석하듯 '이 사건의 핵심은 무엇인지', '앞으로 어떤 영향이 있을지'를 날카롭고 심도 있게 분석하는 글을 작성해줘.대표하는 이미지를 포함해줘",
        "tags": "뉴스분석, 시사트렌드, 앵커브리핑"
    }
}

def generate_content(blog_name, prompt):
    client = genai.Client(api_key=GEMINI_API_KEY)
    print(f"[{blog_name}] 글을 생성 중...")
    
    response = client.models.generate_content(
        model='gemini-2.0-flash',  # 더 안정적인 모델로 변경
        contents=prompt
    )
    full_text = response.text.split('\n', 1)
    title = full_text[0].replace('#', '').strip()
    content = full_text[1].strip() if len(full_text) > 1 else "내용 생성 오류"
    return title, content

def send_to_notion(blog_name, title, content):
    notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties={
            "이름": {"title": [{"text": {"content": title}}]},
            "블로그 명": {"select": {"name": blog_name}},
            "날짜": {"date": {"start": datetime.datetime.now().isoformat()}},
            "상태": {"select": {"name": "대기중"}}
        },
        children=[
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": content[:2000]}}]}
            }
        ]
    )

def main():
    for blog_name, config in BLOG_TYPES.items():
        try:
            title, content = generate_content(blog_name, config["prompt"])
            send_to_notion(blog_name, title, content)
            print(f"✅ {blog_name} 저장 완료")
        except Exception as e:
            print(f"❌ {blog_name} 실패: {e}")

if __name__ == '__main__':
    main()