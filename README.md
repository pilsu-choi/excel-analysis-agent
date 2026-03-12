# Excel Analysis Agent

대용량 엑셀 파일을 자율적으로 분석하여 질문에 답변하는 AI 에이전트

## 특징

- **벡터화 없음**: 데이터를 직접 pandas로 읽어 분석 (RAG 없이 raw 데이터 직접 처리)
- **Agentic 동작**: LangChain DeepAgent 기반, 자율적으로 도구를 선택하고 분석 수행
- **xlsx Skill**: Anthropic Skills의 xlsx 스킬을 통한 Excel 작업 가이드라인 적용
- **FilesystemBackend**: 실제 파일 시스템 접근으로 대용량 파일 처리

## 아키텍처

```
excel_analyze_agent/
├── main.py                    # 메인 CLI 인터페이스
├── create_sample.py           # 테스트용 샘플 엑셀 생성기
├── requirements.txt
├── .env.example
├── data/                      # 분석할 엑셀 파일 위치
└── skills/
    └── xlsx/
        ├── SKILL.md           # xlsx 스킬 정의 (Anthropic Skills 기반)
        └── scripts/
            ├── recalc.py      # LibreOffice 수식 재계산 스크립트
            └── office/
                ├── __init__.py
                └── soffice.py # LibreOffice 헬퍼
```

## 동작 원리

```
사용자 질문
    ↓
DeepAgent (Claude)
    ↓
xlsx Skill 로드 (progressive disclosure)
    ↓
┌─────────────────────────────────┐
│  Built-in Tools (FilesystemBackend) │
│  - ls / glob: 파일 탐색         │
│  - read_file: 파일 읽기         │
│  - execute: Python 코드 실행    │
│    (pandas, openpyxl 활용)      │
│  - write_file: 결과 저장        │
└─────────────────────────────────┘
    ↓
분석 결과 답변
```

## 설치

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. API 키 설정

```bash
cp .env.example .env
# .env 파일을 열어 ANTHROPIC_API_KEY 설정
```

### 3. (선택) LibreOffice 설치 - Excel 수식 재계산이 필요한 경우

```bash
# macOS
brew install --cask libreoffice

# Ubuntu/Debian
sudo apt-get install libreoffice
```

## 사용법

### 샘플 데이터 생성

```bash
python create_sample.py
```

`data/sample_business_data.xlsx` 파일이 생성됩니다:
- **매출데이터**: 5,000행의 거래 데이터
- **직원데이터**: 200명의 직원 정보
- **재고데이터**: 1,000개 SKU의 재고 현황
- **요약분석**: Excel 수식 기반 자동 대시보드

### 에이전트 실행

```bash
python main.py
```

### 사용 예시

```
질문: 전체 매출 현황을 분석해줘
질문: 어떤 제품이 가장 많이 팔렸어?
질문: 지역별 매출을 비교해줘
질문: 2023년 월별 매출 트렌드를 알려줘
질문: 부서별 평균 연봉을 계산해줘
질문: 재고가 부족한 제품 목록을 뽑아줘
질문: 매출 상위 10% 영업사원은 누구야?
질문: 반품률이 높은 제품 카테고리를 찾아줘
```

### 자신의 엑셀 파일 사용

1. `data/` 폴더에 엑셀 파일을 복사
2. `python main.py` 실행
3. 파일명을 언급하며 질문: `"sales_2024.xlsx 파일의 총 매출을 알려줘"`

## 주요 설계 결정

### 벡터화 없이 대용량 파일 처리하는 방법

| 전략 | 설명 |
|------|------|
| **타겟 컬럼 읽기** | `usecols`로 필요한 컬럼만 로드 |
| **청크 읽기** | `nrows`, `skiprows`로 부분 로드 |
| **read_only 모드** | openpyxl의 `read_only=True`로 스트리밍 읽기 |
| **집계 우선** | 전체 데이터를 메모리에 올리기 전 pandas로 집계 |

### Agentic 동작

DeepAgent는 질문에 따라 자율적으로:
1. 어떤 파일을 읽을지 결정
2. 어떤 분석 코드를 실행할지 결정
3. 결과를 어떻게 표현할지 결정
4. 추가 분석이 필요한지 판단

### xlsx Skill

`skills/xlsx/SKILL.md`는 에이전트에게 다음을 안내합니다:
- Excel 파일 작업 베스트 프랙티스
- pandas vs openpyxl 선택 기준
- 하드코딩 대신 Excel 수식 사용 원칙
- 수식 오류 검증 및 수정 방법

## 환경 변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `ANTHROPIC_API_KEY` | ✅ | Anthropic Claude API 키 |
| `LANGCHAIN_TRACING_V2` | ❌ | LangSmith 추적 활성화 |
| `LANGCHAIN_API_KEY` | ❌ | LangSmith API 키 |

## 요구사항

- Python 3.11+
- Anthropic API 키
- (선택) LibreOffice - Excel 수식 재계산 기능 사용 시
# excel-analysis-agent
