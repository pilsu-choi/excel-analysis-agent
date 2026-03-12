"""
Debug Callback Handler
에이전트 실행 흐름을 실시간으로 출력하는 디버그 핸들러
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGenerationChunk, GenerationChunk, LLMResult


# ANSI 색상 코드
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    RED = "\033[31m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"


_ANSI_ESCAPE = re.compile(r"\033\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


def _truncate(text: str, max_len: int = 1000) -> str:
    text = str(text).strip()
    if len(text) > max_len:
        return text[:max_len] + f"  {Color.GRAY}...({len(text) - max_len}자 생략){Color.RESET}"
    return text


def _format_json(obj: Any, max_len: int = 300) -> str:
    try:
        text = json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        text = str(obj)
    return _truncate(text, max_len)


class DebugCallbackHandler(BaseCallbackHandler):
    """
    에이전트 실행 흐름을 콘솔에 출력하는 디버그 핸들러.

    사용 예시:
        from callback_handler import DebugCallbackHandler

        handler = DebugCallbackHandler(verbose=True)
        result = agent.invoke(..., config={"callbacks": [handler]})
    """

    def __init__(
        self,
        verbose: bool = True,
        show_llm_input: bool = False,
        show_token_stream: bool = False,
        max_output_len: int = 300,
        log_file: Optional[str] = None,
    ):
        """
        Args:
            verbose: 전체 디버그 출력 활성화
            show_llm_input: LLM 에 전달되는 메시지 전체 출력
            show_token_stream: 스트리밍 토큰 실시간 출력
            max_output_len: 출력 최대 길이 (글자 수)
            log_file: 로그를 저장할 파일 경로 (None 이면 파일 저장 안 함)
        """
        super().__init__()
        self.verbose = verbose
        self.show_llm_input = show_llm_input
        self.show_token_stream = show_token_stream
        self.max_output_len = max_output_len

        self._llm_start_time: Dict[UUID, float] = {}
        self._tool_start_time: Dict[UUID, float] = {}
        self._chain_depth: int = 0

        self._log_file: Optional[Path] = None
        if log_file:
            self._log_file = Path(log_file)
            self._log_file.parent.mkdir(parents=True, exist_ok=True)
            with self._log_file.open("a", encoding="utf-8") as f:
                f.write(f"\n{'=' * 60}\n")
                f.write(f"  세션 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'=' * 60}\n")

    # ------------------------------------------------------------------ #
    #  내부 헬퍼                                                           #
    # ------------------------------------------------------------------ #

    def _write_log(self, line: str) -> None:
        if self._log_file:
            with self._log_file.open("a", encoding="utf-8") as f:
                f.write(_strip_ansi(line) + "\n")

    def _print(self, label: str, color: str, message: str, indent: int = 0) -> None:
        if not self.verbose:
            return
        prefix = "  " * indent
        line = f"{prefix}{color}{Color.BOLD}[{label}]{Color.RESET} {color}{message}{Color.RESET}"
        print(line)
        self._write_log(f"{prefix}[{label}] {_strip_ansi(message)}")

    def _section(self, title: str, color: str) -> None:
        if not self.verbose:
            return
        bar = "─" * (54 - len(title))
        line = f"\n{color}{Color.BOLD}┌─ {title} {bar}{Color.RESET}"
        print(line)
        self._write_log(f"\n┌─ {title} {'─' * (54 - len(title))}")

    def _end_section(self, color: str) -> None:
        if not self.verbose:
            return
        line = f"{color}{'─' * 58}{Color.RESET}\n"
        print(line)
        self._write_log("─" * 58 + "\n")

    # ------------------------------------------------------------------ #
    #  LLM 이벤트                                                          #
    # ------------------------------------------------------------------ #

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._llm_start_time[run_id] = time.time()
        model = serialized.get("kwargs", {}).get("model_name") or serialized.get("name", "LLM")
        self._section("LLM 호출", Color.CYAN)
        self._print("모델", Color.CYAN, model)
        if self.show_llm_input and prompts:
            self._print("입력", Color.GRAY, _truncate(prompts[0], self.max_output_len))

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._llm_start_time[run_id] = time.time()
        model = (
            serialized.get("kwargs", {}).get("model_name")
            or serialized.get("kwargs", {}).get("model")
            or serialized.get("name", "ChatModel")
        )
        self._section("LLM 호출", Color.CYAN)
        self._print("모델", Color.CYAN, model)

        if self.show_llm_input and messages:
            for msg_list in messages:
                for msg in msg_list:
                    role = getattr(msg, "type", "message")
                    content = _truncate(str(msg.content), self.max_output_len)
                    self._print(f"  ↳ {role}", Color.GRAY, content)

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        if self.show_token_stream:
            print(token, end="", flush=True)

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        elapsed = time.time() - self._llm_start_time.pop(run_id, time.time())

        # tool_calls 추출
        tool_calls: List[str] = []
        for generations in response.generations:
            for gen in generations:
                if isinstance(gen, (ChatGenerationChunk,)) or hasattr(gen, "message"):
                    msg = getattr(gen, "message", None)
                    if msg:
                        calls = getattr(msg, "tool_calls", []) or []
                        for tc in calls:
                            name = tc.get("name", "?") if isinstance(tc, dict) else getattr(tc, "name", "?")
                            tool_calls.append(name)

        if tool_calls:
            self._print("도구 요청", Color.YELLOW, ", ".join(tool_calls))
        else:
            # 일반 텍스트 응답 미리보기
            try:
                text = response.generations[0][0].text
                if text:
                    self._print("출력 미리보기", Color.GREEN, _truncate(text, self.max_output_len))
            except (IndexError, AttributeError):
                pass

        self._print("소요시간", Color.GRAY, f"{elapsed:.2f}s")
        self._end_section(Color.CYAN)

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._llm_start_time.pop(run_id, None)
        self._print("LLM 오류", Color.RED, str(error))
        self._end_section(Color.RED)

    # ------------------------------------------------------------------ #
    #  도구(Tool) 이벤트                                                   #
    # ------------------------------------------------------------------ #

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._tool_start_time[run_id] = time.time()
        tool_name = serialized.get("name", "tool")
        self._section(f"도구 실행: {tool_name}", Color.YELLOW)

        try:
            parsed = json.loads(input_str)
            self._print("입력", Color.YELLOW, _format_json(parsed, self.max_output_len))
        except (json.JSONDecodeError, TypeError):
            self._print("입력", Color.YELLOW, _truncate(input_str, self.max_output_len))

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        elapsed = time.time() - self._tool_start_time.pop(run_id, time.time())
        output_str = output if isinstance(output, str) else str(output)
        self._print("결과", Color.GREEN, _truncate(output_str, self.max_output_len))
        self._print("소요시간", Color.GRAY, f"{elapsed:.2f}s")
        self._end_section(Color.YELLOW)

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._tool_start_time.pop(run_id, None)
        self._print("도구 오류", Color.RED, str(error))
        self._end_section(Color.RED)

    # ------------------------------------------------------------------ #
    #  체인(Chain) 이벤트                                                  #
    # ------------------------------------------------------------------ #

    # def on_chain_start(
    #     self,
    #     serialized: Dict[str, Any],
    #     inputs: Dict[str, Any],
    #     *,
    #     run_id: UUID,
    #     **kwargs: Any,
    # ) -> None:
    #     self._chain_depth += 1
    #     if self._chain_depth == 1:
    #         name = serialized.get("name") or serialized.get("id", ["Chain"])[-1]
    #         self._print("체인 시작", Color.BLUE, name)

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        if self._chain_depth == 1:
            self._print("체인 종료", Color.BLUE, "완료")
        self._chain_depth = max(0, self._chain_depth - 1)

    def on_chain_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._print("체인 오류", Color.RED, str(error))
        self._chain_depth = max(0, self._chain_depth - 1)

    # ------------------------------------------------------------------ #
    #  에이전트 이벤트                                                     #
    # ------------------------------------------------------------------ #

    def on_agent_action(self, action: Any, *, run_id: UUID, **kwargs: Any) -> None:
        tool = getattr(action, "tool", "?")
        tool_input = getattr(action, "tool_input", "")
        self._print(
            "에이전트 액션",
            Color.MAGENTA,
            f"{tool} ← {_truncate(str(tool_input), 120)}",
        )

    def on_agent_finish(self, finish: Any, *, run_id: UUID, **kwargs: Any) -> None:
        output = getattr(finish, "return_values", {}).get("output", "")
        self._print("에이전트 완료", Color.MAGENTA, _truncate(str(output), self.max_output_len))
