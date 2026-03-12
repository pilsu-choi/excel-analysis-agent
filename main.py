"""
Excel Analysis Agent
대용량 엑셀 파일을 자율적으로 분석하여 질문에 답변하는 에이전트
"""

import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_experimental.tools import PythonREPLTool

from callback_handler import DebugCallbackHandler

load_dotenv()

WORKSPACE = Path(__file__).parent
print(WORKSPACE)
SKILLS_DIR = str(WORKSPACE / "skills")
DATA_DIR = WORKSPACE / "data"
skill_content = Path(SKILLS_DIR + "/xlsx/SKILL.md").read_text()
# skills_files = {
#     "/skills/xlsx/SKILL.md": skill_content
# }
SYSTEM_PROMPT = f"""
당신은 대용량 엑셀 파일 분석 전문가입니다.
    
    분석 원칙:
    - 너의 작업 위치는 {WORKSPACE} 입니다.
    - 너는 {DATA_DIR} 디렉토리에 있는 데이터를 사용할 수 있습니다.
    - 10만 행 초과 파일은 반드시 chunksize=10000 청크 처리
    - 벡터화/임베딩 사용 금지, 순수 pandas 연산만 사용
    - 분석 전 항상 write_todos로 단계 계획 수립
    - 중간 결과는 파일시스템에 저장해 컨텍스트 관리
    - 코드 에러 발생 시 원인 파악 후 자동 수정 재시도
    - 최종 결과는 핵심 발견사항 + 인사이트 형식으로 정리
    - 필요한 툴을 사용자의 의견을 묻지 않고 반복적으로 자동 실행 후 최종 결과만 반환
"""
# - 너는 {SKILLS_DIR} 디렉토리에 있는 스킬을 사용할 수 있습니다.
    

def create_agent():
    try:
        from deepagents import create_deep_agent
        from deepagents.backends.filesystem import FilesystemBackend
        from langgraph.checkpoint.memory import MemorySaver
    except ImportError as e:
        print(f"[오류] 필요한 패키지가 설치되지 않았습니다: {e}")
        print("다음 명령어로 설치하세요:")
        print("  pip install -r requirements.txt")
        sys.exit(1)

    # if not os.environ.get("ANTHROPIC_API_KEY"):
    #     print("[오류] ANTHROPIC_API_KEY 환경 변수가 설정되지 않았습니다.")
    #     print(".env 파일을 생성하고 API 키를 설정하세요:")
    #     print("  cp .env.example .env")
    #     print("  # .env 파일에서 ANTHROPIC_API_KEY 설정")
    #     sys.exit(1)

    checkpointer = MemorySaver()

    agent = create_deep_agent(
        model="openai:gpt-4.1",
        backend=FilesystemBackend(root_dir=str(WORKSPACE)),
        skills=[SKILLS_DIR + "/"],
        checkpointer=checkpointer,
        system_prompt=SYSTEM_PROMPT,
        tools=[PythonREPLTool()],
    )

    return agent, checkpointer


def list_excel_files() -> list[str]:
    files = []
    for pattern in ["*.xlsx", "*.xlsm", "*.csv", "*.tsv"]:
        files.extend(DATA_DIR.glob(pattern))
    return [str(f.relative_to(WORKSPACE)) for f in sorted(files)]


def print_banner():
    print("\n" + "=" * 60)
    print("  Excel Analysis Agent")
    print("  대용량 엑셀 파일 자율 분석 에이전트")
    print("=" * 60)
    print(f"  워크스페이스: {WORKSPACE}")
    print(f"  데이터 디렉토리: {DATA_DIR}")
    print("=" * 60)

    excel_files = list_excel_files()
    if excel_files:
        print("\n  발견된 엑셀/CSV 파일:")
        for f in excel_files:
            print(f"    - {f}")
    else:
        print("\n  [안내] data/ 디렉토리에 엑셀 파일이 없습니다.")
        print("  엑셀 파일을 data/ 폴더에 넣거나,")
        print("  python create_sample.py 로 샘플 파일을 생성하세요.")

    print("\n  명령어: 'exit' 또는 'quit' 으로 종료")
    print("          'new' 로 새 대화 시작")
    print("          'files' 로 파일 목록 확인")
    print("=" * 60 + "\n")


def format_response(result: dict) -> str:
    messages = result.get("messages", [])
    if not messages:
        return "(응답 없음)"

    last_msg = messages[-1]
    if hasattr(last_msg, "content"):
        content = last_msg.content
        if isinstance(content, list):
            text_parts = [
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            ]
            return "\n".join(text_parts).strip()
        return str(content).strip()
    return str(last_msg).strip()


def main():
    print_banner()

    print("에이전트를 초기화하는 중...")
    agent, _ = create_agent()
    print("에이전트 초기화 완료!\n")

    log_dir = WORKSPACE / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    print(f"  로그 파일: {log_path}\n")

    debug_handler = DebugCallbackHandler(
        verbose=True,
        show_llm_input=False,   # True 로 바꾸면 LLM 입력 메시지 전체 출력
        show_token_stream=False, # True 로 바꾸면 스트리밍 토큰 실시간 출력
        max_output_len=300,
        log_file=str(log_path),
    )

    thread_id = str(uuid.uuid4())

    while True:
        try:
            user_input = input("질문: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n종료합니다.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "종료"):
            print("종료합니다.")
            break

        if user_input.lower() in ("new", "새로"):
            thread_id = str(uuid.uuid4())
            print("[새 대화 시작]\n")
            continue

        if user_input.lower() in ("files", "파일"):
            excel_files = list_excel_files()
            if excel_files:
                print("\n현재 파일 목록:")
                for f in excel_files:
                    print(f"  - {f}")
            else:
                print("data/ 디렉토리에 파일이 없습니다.")
            print()
            continue

        print("\n에이전트 분석 중...\n")
        try:
            result = agent.invoke(
                {
                    "messages": [
                        {"role": "user", "content": user_input}
                    ],
                    # Seed the default StateBackend's in-state filesystem (virtual paths must start with "/").
                    # "files": skills_files
                },
                config={
                    "configurable": {"thread_id": thread_id},
                    "callbacks": [debug_handler],
                },
            )

            response = format_response(result)
            print(f"에이전트: {response}\n")
            print("-" * 60 + "\n")

        except KeyboardInterrupt:
            print("\n\n[중단됨] 다음 질문을 입력하세요.\n")
        except Exception as e:
            print(f"\n[오류] {e}\n")


if __name__ == "__main__":
    main()
