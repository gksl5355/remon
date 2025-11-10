# Python 코드 주석 및 Docstring 표준 (Google Style 기반)

## 1\. 목적

프로젝트 전반에서 일관된 주석, docstring, 코드 헤더 스타일을 유지하기 위한 기준. Google Python Style Guide를 기반으로 하되, 실무에서 불필요한 형식은 최소화한다.

---

## 2\. 기본 원칙

* 가독성과 유지보수성을 최우선으로 한다.  
* Docstring은 “무엇을 하는가”에 집중한다.  
* 외부 공개 함수는 반드시 Docstring을 작성한다.  
* 내부용(`_` prefix) 함수는 필요할 때만 Docstring을 작성하고, 주로 한 줄 주석으로 대체한다.  
* 한 줄 주석은 “왜 이 로직이 필요한가”를 중심으로 쓴다.

---

## 3\. 파일 헤더 주석 (Module Header)

"""

module: report\_service.py

description: 리포트 생성, 조회 및 관련 비즈니스 로직을 처리하는 서비스 계층

author: 홍길동

created: 2025-11-07

updated: 2025-11-07

dependencies:

    \- app.config.logger

    \- app.models.report

"""

---

## 4\. 클래스 Docstring

class ReportService:

    """

    리포트 관련 비즈니스 로직을 처리하는 서비스 클래스.

    Responsibilities:

        \- 리포트 생성

        \- 리포트 조회 및 요약 반환

    Example:

        \>\>\> service \= ReportService()

        \>\>\> result \= await service.generate\_report({"user\_id": 1})

        \>\>\> print(result\["summary"\])

    """

---

## 5\. 함수 및 메서드 Docstring 기본 구조 (Google Style)

def function\_name(param1: Type, param2: Type \= None) \-\> ReturnType:

    """

    함수의 핵심 목적을 한 줄로 설명.

    Args:

        param1 (Type): 설명.

        param2 (Type, optional): 설명. 기본값은 None.

    Returns:

        ReturnType: 반환값 설명.

    Raises:

        ValueError: 조건이 맞지 않는 경우.

    """

---

## 6\. 함수 유형별 예시

### 6.1 외부 공개용 서비스 함수

async def generate\_report(self, data: dict) \-\> dict:

    """

    주어진 데이터를 기반으로 리포트를 생성한다.

    Args:

        data (dict): 리포트 생성에 필요한 입력 데이터.

    Returns:

        dict: 생성된 리포트의 ID와 요약 결과.

    """

    report \= await self.\_process\_report\_data(data)

    return {"report\_id": report.id, "summary": report.summary}

---

### 6.2 내부 로직 처리 함수

async def \_process\_report\_data(self, data: dict):

    """리포트 생성 전 데이터 정제 및 분석."""

    \# 1\. 데이터 검증

    \# 2\. 데이터 가공

    \# 3\. 분석 결과 생성

    ...

---

### 6.3 공용 유틸 함수

def format\_date\_range(start: str, end: str) \-\> str:

    """

    시작일과 종료일을 포맷팅하여 범위 문자열을 반환한다.

    Args:

        start (str): 시작 날짜 (예: "2025-01-01").

        end (str): 종료 날짜 (예: "2025-03-31").

    Returns:

        str: "2025-01-01 \~ 2025-03-31" 형식의 문자열.

    """

    return f"{start} \~ {end}"

---

### 6.4 전역 리소스 접근 함수 (DB, Redis, API 등)

async def cache\_report\_summary(report\_id: int, summary: str, ttl: int \= 300):

    """

    리포트 요약 정보를 Redis에 캐시한다.

    Args:

        report\_id (int): 리포트 ID.

        summary (str): 캐시할 요약 문자열.

        ttl (int, optional): 캐시 만료 시간(초). 기본값은 300\.

    Side Effects:

        \- Redis에 키 저장 (key: "report:{report\_id}:summary").

    """

    await redis.setex(f"report:{report\_id}:summary", ttl, summary)

---

### 6.5 데이터 검증 및 변환 함수

def normalize\_user\_input(data: dict) \-\> dict:

    """

    사용자 입력 데이터를 표준화한다.

    Args:

        data (dict): 원본 입력 데이터.

    Returns:

        dict: 소문자 키로 정규화된 데이터.

    """

    return {k.lower(): v for k, v in data.items()}

---

### 6.6 환경 설정 접근 함수

from app.config.settings import settings

def get\_database\_url() \-\> str:

    """

    현재 환경의 데이터베이스 URL을 반환한다.

    Returns:

        str: DATABASE\_URL 값.

    """

    return settings.DATABASE\_URL

---

### 6.7 예외 발생 가능 함수

async def fetch\_external\_report(api\_url: str) \-\> dict:

    """

    외부 API에서 리포트 데이터를 조회한다.

    Args:

        api\_url (str): 호출할 API 엔드포인트 URL.

    Returns:

        dict: 외부 API 응답 JSON 데이터.

    Raises:

        ConnectionError: 네트워크 연결 실패 시.

        ValueError: 응답 데이터 형식이 잘못된 경우.

    """

    ...

---

### 6.8 단순 내부 헬퍼 함수

def \_to\_snake\_case(s: str) \-\> str:

    \# CamelCase → snake\_case 변환

    ...

---

## 7\. 상수 및 변수 주석

DEFAULT\_REPORT\_TYPE \= "summary"  \# 기본 리포트 유형

CACHE\_TTL \= 300  \# Redis 캐시 만료시간(초)

---

## 8\. 권장 스타일 요약표

| 함수 유형 | Docstring | 내용 수준 | 예시 |
| :---- | :---- | :---- | :---- |
| 외부 서비스 함수 | 필수 | Args / Returns | `generate_report` |
| 내부 로직 (`_`) | 선택 | 한 줄 요약 | `_process_report_data` |
| 공용 유틸 | 필수 | 간결한 Args/Returns | `format_date_range` |
| 전역 리소스 접근 | 필수 | Side Effects 포함 | `cache_report_summary` |
| 검증/변환 | 필수 | Args/Returns | `normalize_user_input` |
| 단순 헬퍼 | 생략 | 주석 1줄 | `_to_snake_case` |

## **9\. 로깅 (Logging) 가이드라인 (신규 추가)**

### **9.1. 기본 원칙**

1. **표준 모듈 사용:** Python의 내장 `logging` 모듈을 사용합니다.  
2. **`print()` 금지:** 서버 애플리케이션(FastAPI 등) 코드에서 `print()` 사용을 **엄격히 금지**합니다. `print()`는 비동기 환경에서 출력을 보장하지 않으며, 로그 레벨 관리가 불가능합니다.

**모듈 단위 로거:** 각 파일(`*.py`) 상단에 모듈 레벨 로거를 선언합니다.  
import logging  
logger \= logging.getLogger(\_\_name\_\_)

3.   
4. **로그 레벨 준수:** 상황에 맞는 로그 레벨(Level)을 명확히 구분하여 사용합니다.  
5. **민감 정보 금지:** **절대로** API 키, 비밀번호, 개인정보(이름, 이메일) 등 민감 정보를 로그에 남기지 않습니다.

### **9.2. 로그 레벨 기준**

* **`logger.DEBUG`**  
  * **목적:** 개발 및 디버깅 시에만 필요한 상세 정보.  
  * **예시:** `logger.debug(f"Request body received: {data}")`, `logger.debug(f"Vector search results count: {len(docs)}")`  
* **`logger.INFO`**  
  * **목적:** 시스템의 주요 상태 변경 및 정상적인 핵심 흐름을 나타냅니다. (운영 환경에서 주로 확인)  
  * **예시:** `logger.info("FastAPI server started.")`, `logger.info(f"User {user_id} requested report {report_id}.")`, `logger.info(f"PDF file '{filename}' uploaded and vectorized.")`  
* **`logger.WARNING`**  
  * **목적:** 예상치 못한 일이 발생했으나, 아직 오류는 아니며 서비스는 정상 작동 중인 상태. (주의 필요)  
  * **예시:** `logger.warning(f"External API call took 5.2s (Threshold: 5s).")`, `logger.warning("Cache miss for translation key.")`  
* **`logger.ERROR`**  
  * **목적:** 심각한 문제로 인해 특정 기능이 **실패**했음을 의미합니다. (즉각적인 확인 필요)  
  * **예시:** `logger.error(f"Failed to connect to database: {e}")`, `logger.error("RAG query failed for user {user_id}.")`  
* **`logger.CRITICAL`**  
  * **목적:** 시스템 전체가 중단될 수 있는 매우 치명적인 오류. (즉시 조치 필요)  
  * **예시:** `logger.critical("Failed to load OpenAI API key. Application shutting down.")`

### **9.3. 로깅 방법론**

1. **예외(Exception) 처리:**  
   * `try...except` 블록에서 오류를 잡을 때는 `logger.error` 또는 `logger.exception`을 사용합니다.  
   * 스택 트레이스 전체를 포함하려면 `exc_info=True` 옵션을 사용하거나 `logger.exception`을 사용합니다.

try:  
    result \= 1 / 0  
except ZeroDivisionError as e:  
    \# exc\_info=True: 오류 상세 내역(Traceback)을 로그에 포함  
    logger.error(f"Arithmetic error occurred: {e}", exc\_info=True)

\# 또는 logger.exception (ERROR 레벨로 자동 설정됨)  
try:  
    await external\_api.call()  
except Exception as e:  
    \# exception은 error 레벨이며 exc\_info=True가 기본값  
    logger.exception(f"Failed to call external API for report {report\_id}: {e}")

2. **컨텍스트(Context) 포함:**  
   * "Failed"라는 로그만으로는 원인을 알 수 없습니다. `user_id`, `report_id`, `filename` 등 문제 추적에 필요한 **컨텍스트 정보**를 반드시 함께 기록합니다.  
   * **(Bad)** `logger.error("File processing failed.")`  
   * **(Good)** `logger.error(f"File processing failed for user_id={user_id}, filename='{filename}'.")`  
3. **성능 로깅:**  
   * `time` 모듈을 사용하여 주요 함수의 시작과 끝에 `INFO` 또는 `DEBUG` 레벨 로그를 기록하면 성능 모니터링에 유용합니다.

import time  
start\_time \= time.time()  
logger.debug("Starting RAG context retrieval...")

\# ... (작업 수행) ...

elapsed \= time.time() \- start\_time

4. logger.info(f"RAG context retrieval finished in {elapsed:.2f}s.")

## **10\. 타입 힌팅 (Type Hinting) 가이드라인**

### **10.1. 기본 원칙**

* 모든 함수/메서드의 \*\*인자(Arguments)\*\*와 \*\*반환값(Return)\*\*에 타입 힌트를 명시합니다.  
* 변수 선언 시에도 타입을 명시하여 IDE의 추론을 돕습니다.  
* \*\*`Mypy`\*\*를 Linter와 함께 사용하여 커밋 전에 타입 오류를 검사합니다.

### **10.2. 최신 문법 사용 (Python 3.10+ 기준)**

* `typing` 모듈 임포트를 최소화하고 \*\*내장 제네릭 타입(Built-in Generics)\*\*을 사용합니다.  
  * `List[str]` (X) → `list[str]` (O)  
  * `Dict[str, int]` (X) → `dict[str, int]` (O)  
* **Union 타입**은 `|` 연산자를 사용합니다.  
  * `Optional[str]` (X) → `str | None` (O)  
  * `Union[str, int]` (X) → `str | int` (O)

**예시:**  
\# Bad (Old Style)  
from typing import List, Optional, Dict  
def get\_user(user\_id: int) \-\> Optional\[Dict\]:  
    ...

\# Good (Modern Style)  
def get\_user(user\_id: int) \-\> dict | None:  
    ...

* users: list\[str\] \= \["alice", "bob"\]

**11\. 테스트 (Testing) 가이드 라인**

### **11.1. 기본 원칙 (Pytest)**

* **프레임워크:** **`pytest`** 사용을 표준으로 합니다.  
* **AAA 패턴:** 모든 테스트는 **Arrange(준비) \- Act(실행) \- Assert(검증)** 구조를 따릅니다.  
* **독립성:** 테스트는 **서로 독립적**이어야 하며, 실행 순서에 의존해서는 안 됩니다.

