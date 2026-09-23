# Pterodactyl MCP

Pterodactyl Client API를 사용하는 로컬 stdio MCP입니다. 파일 관리·복원, 게임 서버 제어, 콘솔 수집·명령 실행 등 20개 도구를 제공합니다.
공식 Python MCP SDK 1.x 유지보수 버전을 사용합니다. Panel/Wings 설치나 서버 재시작은 필요하지 않습니다.

특정 커뮤니티나 게임에 종속되지 않습니다. Pterodactyl이 관리하는 서버의 공통 파일·전원·콘솔 API를 사용하며, 게임 전용 플러그인이나 RCON 연결은 요구하지 않습니다.
파일 경로와 콘솔 명령은 해당 게임에 맞게 지정해야 합니다. 정상 종료 동작과 콘솔 입력 지원은 서버의 Egg 및 실행 설정을 따릅니다.
게임별 실제 동작을 모두 검증했다는 의미는 아니며, `running` 상태만으로 게임 로딩 완료를 판정하지 않습니다.

## 설치

Python 3.11 이상이 필요합니다. 저장소를 내려받은 뒤 프로젝트 폴더에서 실행합니다.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
if (-not (Test-Path config.local.json)) { Copy-Item config.example.json config.local.json }
```

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
test -e config.local.json || cp config.example.json config.local.json
```

## 키 설정

1. `config.local.json`의 `panel_url`을 사용하는 패널 주소로 바꿉니다.
2. 패널에 로그인하고 `/account/api` 경로를 엽니다.
3. Description에 `MCP 파일 관리`를 넣고 Client API 키를 생성합니다.
4. `config.local.json`의 빈 `api_key`에 저장합니다. 키를 채팅, 소스 저장소에 올리지 마세요.
5. 읽기 전용 연결 확인: `.\.venv\Scripts\python.exe pterodactyl_mcp.py --check`

Linux/macOS에서는 Python 실행 경로를 `.venv/bin/python`으로 바꿉니다.

설정 파일은 매 요청마다 읽으므로 키를 넣거나 바꾼 뒤 MCP 재시작은 필요하지 않습니다.
`PTERODACTYL_API_KEY` 환경변수가 있으면 파일의 키보다 우선합니다.
HTTP 주소는 API 키와 파일 전송을 암호화하지 않습니다. 가능하면 HTTPS 패널 주소를 사용하세요.

## 공유할 때

저장소의 `config.example.json`은 주소 예제와 빈 API 키만 제공합니다. 사용자는 자신의 패널 주소·키·서버 별칭을 설정합니다.
실제 `config.local.json`, 로컬 Codex 설정, 수집 로그, 백업, 전송 파일은 Git에서 제외합니다. 로컬 폴더에는 이 데이터가 있을 수 있으므로 폴더 전체를 압축해 공유하지 마세요.
소스 공유에는 GitHub 저장소 또는 GitHub에서 내려받은 소스 ZIP을 사용합니다. Git 작성자와 저장소 소유자의 계정 정보는 GitHub에 표시될 수 있습니다.

## Codex 연결

프로젝트 폴더에서 `python register_codex.py`를 실행합니다.
현재 설치 경로의 가상환경과 MCP 실행 파일을 사용자 `~/.codex/config.toml`에 등록합니다. `CODEX_HOME`도 지원합니다.
기존 설정은 같은 폴더의 `config.toml.before-pterodactyl-*`에 백업하며, 다른 설정의 동명 MCP가 있으면 덮어쓰지 않고 중단합니다.
다른 MCP 클라이언트는 `.venv`의 Python을 실행 명령으로, `pterodactyl_mcp.py`의 절대 경로를 인자로 등록합니다. 전송 방식은 stdio입니다.
공식 설정 문서: https://developers.openai.com/codex/mcp
새 대화 또는 MCP 재연결 후 도구가 표시되는지 확인합니다.

## 도구

| 도구 | 기능 |
| --- | --- |
| list_servers | 접근 가능한 서버 이름과 ID |
| list_files | 폴더 내용 조회: 페이지(offset/limit), 이름 패턴, 정렬, 폴더 크기 합산 |
| read_file | UTF-8 텍스트와 SHA-256 조회, 최대 2 MiB |
| write_file | 텍스트 생성/수정, 원본 백업, 결과 재조회 |
| download_file | 바이너리/텍스트를 로컬 transfers에 다운로드, 최대 2 GiB |
| upload_file | transfers의 파일을 서버에 업로드, 최대 2 GiB |
| create_directory | 폴더 생성 |
| move_file | 파일/폴더 이동, 이름 변경 |
| copy_file | 파일 복사(폴더 제외), 기본 이름 `이름 copy.확장자` 또는 지정 경로 |
| compress_files | 같은 폴더의 파일/폴더를 .tar.gz로 압축, 선택적 저장 경로 |
| decompress_file | zip·tar.gz·7z·rar·단일 .gz 등을 새 폴더에 압축 해제 |
| trash_file | 삭제 대신 서버의 /.mcp-trash로 이동, 원래 경로 기록 |
| list_trash | 휴지통 항목의 원래 경로·버린 시각·경과 일수·크기(폴더는 재귀 합산) |
| restore_trash | 휴지통 항목을 기록된 원래 경로 또는 지정 경로로 복구 |
| empty_trash | 휴지통 항목 영구 삭제(이름 지정 또는 N일 경과), 미리보기 지원 |
| get_server_status | 실행 상태와 CPU·메모리 등 자원 사용량 조회 |
| start_server | 게임 서버 시작 요청 |
| restart_server | 게임 서버 재시작 요청 |
| stop_server | 게임 서버 정상 종료 요청 |
| capture_console | 요청 시 정해진 시간 동안 콘솔 원문 저장 및 요약 |
| read_console_capture | 저장된 콘솔 로그의 줄 단위 조회·문자열 검색 |
| diagnose_connection | 연결된 계정·서버 권한·Wings 연결 진단 |
| list_console_captures | 서버·기간별 로컬 콘솔 수집 기록 목록 |
| list_file_backups | 원래 서버·경로별 로컬 파일 백업 목록 |
| restore_file_backup | 백업 무결성 확인 및 현재 파일 보관 후 원래 경로로 복원 |
| send_console_command | 게임 콘솔 명령 실행 및 선택적 응답 관찰 |

`list_servers`에서 확인한 identifier를 사용합니다. `server_aliases`에 `"my-server": "실제 ID"` 같은 별칭도 추가할 수 있습니다. 아래 `my-server`는 사용자가 설정해야 하는 예제 별칭입니다.
서버 경로는 Pterodactyl 파일 관리자에 보이는 루트를 기준으로 합니다. 아래 `/path/to/config.txt`는 실제 게임의 설정 파일 경로로 바꿔 사용합니다.

텍스트 수정은 먼저 읽은 파일의 `sha256`을 `expected_sha256`으로 전달해야 합니다.
원본은 `backups/<서버 ID>/<시각-고유값>/original.bin`에 저장하고, `metadata.json`에 원래 경로와 해시를 기록합니다.
백업에 실패하면 수정하지 않습니다. `verified: false`이면 수정 후 재조회한 내용이 예상과 다르므로 확인해야 합니다.
읽기/쓰기는 원본의 BOM과 줄바꿈을 보존해야 하며, UTF-8이 아닌 파일은 다운로드해 원래 인코딩으로 편집 후 업로드합니다.

업로드는 기존 경로를 덮어쓰지 않습니다. 교체할 파일을 먼저 이름 변경하거나 휴지통으로 옮겨 보관한 뒤 업로드합니다.
다운로드도 기존 로컬 파일을 덮어쓰지 않습니다. 전송은 메모리에 전체 파일을 올리지 않지만 네트워크/서버 제한과 도구 시간 제한의 영향을 받습니다.
로컬 업로드/다운로드 범위는 설정의 `transfer_directory` 내부로 제한합니다.

`list_files`는 한 번에 최대 `limit`개(기본 100, 최대 1000)를 돌려주며 `total`·`matched`와 다음 페이지의 `next_offset`(마지막이면 null)을 함께 반환합니다.
`pattern`은 대소문자를 구분하는 glob(`*.so`)이고, `sort`는 `name`(폴더 먼저)·`size`·`modified`, `descending=true`로 역순입니다.
기본 출력은 이름·종류·크기·수정 시각만 포함하며 `details=true`면 Wings의 모든 필드를 돌려줍니다. 폴더 크기는 `folder_sizes=true`일 때만 하위까지 합산하고, 조회 횟수 상한에 걸리면 `size_complete: false`(최소값)로 표시합니다.
Wings는 없는 폴더에도 HTTP 500을 돌려주므로, 500이 나면 상위 폴더를 확인해 `Directory does not exist`/`Not a directory`로 구분하고, 폴더가 있으면 일시적 오류로 보고 한 번만 다시 조회합니다.

복사·압축·해제는 기존 파일을 덮어쓰지 않습니다. `copy_file`은 일반 파일만 복사하며, 폴더는 `compress_files`로 보관합니다.
`compress_files`는 Wings가 만드는 tar.gz만 지원하므로 `destination`은 `.tar.gz` 또는 `.tgz`로 끝나야 합니다.
Wings는 압축을 풀 때 같은 이름의 기존 파일을 덮어씁니다. 그래서 `decompress_file`은 존재하지 않는 새 폴더에만 풀고, 작업 중 아카이브를 그 폴더로 잠시 옮겼다가 원래 경로로 되돌립니다.
플러그인 배포는 새 폴더에 풀고 내용을 확인한 뒤, 교체할 파일을 `trash_file`로 옮기고 `move_file`로 제자리에 놓습니다.
압축·해제 요청은 150초 후 응답을 기다리지 않지만 Wings에서는 계속 진행될 수 있으므로, 시간 초과 시 폴더를 확인한 뒤 다시 시도합니다.

`trash_file`은 항목을 `/.mcp-trash/<시각-고유값>-<이름>`으로 옮기고, 원래 경로를 `/.mcp-trash/<시각-고유값>.json`에 기록합니다.
`list_trash`로 항목과 크기를 확인하고 `restore_trash(server, entry)`로 원래 경로에 복구합니다. 기록이 없는 이전 항목은 `destination`을 지정합니다.
`empty_trash`는 `/.mcp-trash` 안의 항목만 영구 삭제하며 되돌릴 수 없습니다. `entries`(목록의 이름) 또는 `older_than_days`(0이면 시각이 붙은 모든 항목) 중 하나만 지정하고, `dry_run=true`로 먼저 확인합니다. 이름이 하나라도 없으면 아무것도 삭제하지 않습니다.
자동 파일 백업은 `list_file_backups`에서 찾고 `restore_file_backup`으로 복원합니다. 아래 복원 절차를 참고하세요.
로컬 백업과 휴지통은 자동 정리하지 않으므로 디스크 공간을 차지합니다. 휴지통은 `empty_trash`로 비웁니다.

강제 종료(kill), 휴지통 밖 파일의 영구 삭제, 사용자 생성, 서버 생성 전용 도구는 포함하지 않습니다.
Pterodactyl API에는 조건부 원자적 쓰기가 없으므로 해시 확인과 쓰기 사이에 외부 프로그램이 수정하는 경쟁 상황까지 막지는 못합니다.
동일 파일의 동시 편집을 피하세요. API 키의 권한은 해당 패널 계정의 서버 접근 권한을 따릅니다.

## 서버 시작·종료와 권한

`start_server`, `restart_server`, `stop_server`는 기존 Client API 키를 사용합니다.
`server`에 직접 설정한 별칭이나 서버 ID를 지정합니다. 정지·재시작 시 접속자가 연결 해제됩니다.
제어 대상은 해당 게임 서버 컨테이너이며 호스트 컴퓨터나 Wings 서비스가 아닙니다.
기본 `wait_seconds=0`에서는 `accepted: true`가 API 요청 수락만 뜻합니다.
`start_server(server="my-server", wait_seconds=30)`, `restart_server`, `stop_server`는 요청 수락 후 최대 30초 동안 완료 상태를 확인합니다. 대기 범위는 0~60초입니다.
시작은 `running`, 정지는 `offline` 관찰 시 `completed=true`를 반환합니다. 재시작은 실행 상태로 돌아온 것 외에 중간 상태 전환이나 가동 시간 감소도 관찰해야 완료로 표시합니다.
빠른 재시작이 조회 사이에 끝나 그 증거를 놓치면 실제로 재시작했어도 `completed=false`일 수 있습니다. 이때 자동으로 다시 재시작하지 않습니다.
대기 시간 초과와 상태 조회 실패를 구분하고, 요청 수락 여부를 유지해서 반환합니다. 이후 상태는 `get_server_status`로 확인합니다.
`running`도 게임 로딩 및 플레이어 접속 준비 완료를 보장하지 않습니다. 시간 초과 시 상태부터 확인하고 재시작을 무조건 반복하지 않습니다.

일반 부사용자는 각각 `control.start`, `control.restart`, `control.stop` 권한이 필요합니다.
서버 소유자와 패널 관리자는 Pterodactyl 서버 권한 정책을 따릅니다.
실제 권한은 API 키를 발급한 계정의 권한을 따릅니다. 사용자·서버 생성은 Application API 확장이 필요하며 현재 MCP에는 구현하지 않았습니다.
키 종류 및 관리자 API 권한 처리는 패널 버전에 따라 다르므로 별도 Application API 키가 필요한 설치도 있습니다.

Power API: https://github.com/pterodactyl/panel/blob/1.0-develop/app/Http/Controllers/Api/Client/Servers/PowerController.php
권한 정책: https://github.com/pterodactyl/panel/blob/1.0-develop/app/Policies/ServerPolicy.php

## 연결·계정·권한 진단

`diagnose_connection()`은 패널 연결과 현재 API 계정의 ID·이름·관리자 여부를 확인합니다.
`diagnose_connection(server="my-server")`는 해당 서버의 실제 권한 목록, 소유자 여부, Wings 자원 조회와 실행 상태도 확인합니다.
`ok`, `stage`, `error.code`로 설정 오류, 인증 실패, 권한 부족, 연결 실패, 호출 제한 등을 구분합니다.
API 키, 이메일, 원본 오류 응답은 결과에 포함하지 않습니다. 진단은 읽기 전용이며 서버 전원이나 파일을 변경하지 않습니다.

## 자동 파일 백업 찾기·복원

1. `list_file_backups(server="my-server", path="/path/to/config.txt")`로 백업 ID와 원래 경로를 확인합니다.
2. 대상 파일이 있다면 `read_file`로 현재 SHA-256을 확인합니다. 바이너리는 `download_file`의 SHA-256을 사용할 수 있습니다.
3. `restore_file_backup(server="my-server", backup_id="목록의 ID", expected_sha256="현재 해시")`를 호출합니다. 대상 파일이 없으면 해시를 생략합니다.

백업은 원래 서버·경로로만 복원하며, 다른 서버를 지정하면 거부합니다. 원본 바이트와 저장된 해시를 대조하고, 기존 대상도 새 백업으로 저장한 다음 복원합니다.
기존 파일이 바뀌었거나 백업 저장에 실패하면 덮어쓰지 않습니다. 복원 후 재조회한 바이트가 일치해야 `restored=true`입니다.
이 기능은 MCP가 파일 수정 전 생성한 로컬 백업용이며, Pterodactyl 전체 서버 백업이나 휴지통 복원과는 별개입니다.
목록은 최신순이고 `offset`, `limit`(최대 100), `next_offset`으로 나눠 조회합니다. 손상된 메타데이터는 `skipped_invalid`로 집계합니다.

## 요청 시 콘솔 수집

`capture_console(server="my-server", seconds=30)`은 연결·인증 후 30초 동안 콘솔을 수집하고 연결을 닫습니다.
기본 30초, 허용 범위는 1~60초입니다. 상시 수집 서비스는 실행하지 않으며, 게임 명령이나 전원 신호도 보내지 않습니다.
`websocket.connect` 권한과 MCP 실행 컴퓨터에서 Wings WebSocket 주소에 접근할 수 있는 연결이 필요합니다.

저장 위치는 설정 파일 옆 `captures/<capture_id>/`이며 MCP가 실행되는 로컬 컴퓨터에 생성합니다.

- `events.jsonl`: 이벤트 종류, 로컬 UTC 수신 시각, 수신한 원문 문자열 배열. ANSI 색상 코드와 줄바꿈을 보존합니다. 인증 토큰과 통계 이벤트는 저장하지 않습니다.
- `console.log`: 사람이 읽을 원문. 각 이벤트의 문자열 사이에 필요한 줄바꿈을 추가합니다.
- `metadata.json`: 수집 범위, 종료 이유, 원문 위치, 반복 메시지 횟수, 오류·경고 후보와 앞뒤 2줄.

`include_recent=false`가 기본이며 연결 이후 출력만 수집합니다.
`include_recent=true`는 Wings에 남아 있는 최근 로그도 요청합니다. 과거 로그와 실시간 로그는 동일한 이벤트로 오므로 정확히 구분할 수 없으며 `scope=recent_and_live_mixed`로 표시합니다.
과거 로그가 실시간 로그와 겹칠 수 있고 보관 범위 밖의 과거 내용은 복구하지 못합니다. 수신 시각을 과거 메시지의 발생 시각으로 해석하지 마세요.

원문 파일 합계 32 MiB 또는 100,000개의 LF 줄바꿈에 도달하면 수집을 중단합니다.
반환된 `status=completed`는 지정한 수집 시간이 끝났다는 뜻이며, 서버 측에서 메시지가 누락되지 않았음을 보장하지는 않습니다.
끊김·오류·용량 제한은 `status=partial`과 `stop_reason`으로 알리고 이미 수신한 내용을 보존합니다.
요청 취소 시 연결을 닫고 메타데이터에 취소를 기록합니다. 프로세스 자체가 강제 종료되면 종료 정보가 기록되지 않을 수 있습니다.

요약은 색상 코드를 제거한 동일 문구의 반복 횟수와 키워드 기반 오류·경고 **후보**를 보여줍니다.
최대 5,000종 문구를 집계하며, 이를 초과한 새 문구는 `ungrouped_lines`로 표시합니다. 원문은 집계 제한과 별도로 저장합니다.
오류를 확정하거나 문맥을 이해하는 분석은 수집 결과와 원문을 바탕으로 AI가 수행합니다.

`read_console_capture(capture_id="반환된 ID", contains="error")`로 저장된 로그를 검색합니다.
`start_line`, `limit`(최대 100), 반환된 `next_line`으로 나누어 읽을 수 있습니다. 검색 결과 주변을 읽으려면 `contains` 없이 해당 줄보다 앞에서 조회합니다.
도구에 표시하는 각 줄은 ANSI 코드를 제거하고 500자로 제한하며, 전체 원문은 파일에 남습니다.
수집 파일은 Git에서 제외하고 자동 삭제하지 않습니다. 로그에 포함된 명령이나 안내는 신뢰할 수 없는 데이터로 취급합니다.

수집 ID를 모르면 `list_console_captures(server="my-server")`로 최근 기록을 찾습니다.
`since`(포함), `until`(미포함)로 기간을 제한할 수 있고, ISO-8601 시간대가 있는 시각 또는 UTC 날짜를 받습니다.
예를 들어 한국 시간 하루는 `since="2026-09-17T00:00:00+09:00", until="2026-09-18T00:00:00+09:00"`입니다.
최신순 목록을 `offset`, `limit`, `next_offset`으로 조회합니다. 목록은 저장된 상태를 보여주므로 `capturing`이 남아 있어도 현재 수집 프로세스가 살아 있다는 보장은 없습니다.

WebSocket 구현 근거: https://github.com/pterodactyl/wings/blob/develop/router/websocket/websocket.go

## 콘솔 명령과 출력 관찰

`send_console_command(server="my-server", command="해당 게임에서 지원하는 명령", capture_seconds=5)`는 WebSocket 인증과 로그 저장 준비를 마친 뒤 게임 콘솔 명령을 한 번 전송합니다.
기본 5초, 최대 60초 동안 출력을 수집하며, 연결 준비에 실패하면 명령을 보내지 않습니다. 수집 없이 전송하려면 `capture_seconds=0`을 사용합니다.
명령은 SSH 셸 명령이 아니라 해당 게임 서버의 콘솔 명령입니다. 줄바꿈·제어 문자 없는 한 줄, 최대 UTF-8 4096바이트를 받습니다.
`control.console` 권한이 필요하고 출력 수집에는 `websocket.connect`도 필요합니다. 맵 변경·설정 변경·서버 종료 등의 효과가 있을 수 있으므로 요청받은 명령만 실행합니다.

`dispatch_attempted`는 전송 시도 여부, `accepted`는 API 수락 여부입니다. 응답 시간 초과 등으로 결과를 알 수 없으면 `accepted=null`입니다.
`accepted=true`여도 잘못된 게임 명령일 수 있으므로 `effect_verified`는 자동으로 참이 되지 않습니다. 수집된 콘솔에는 다른 활동도 섞일 수 있습니다.
중복 실행을 피하기 위해 실패나 시간 초과 후 명령을 자동 재전송하지 않습니다. 출력과 상태를 확인한 다음 판단합니다.

공유 저장소에는 실행 코드·설치 설정·설명서만 포함합니다.
`config.local.json`, 로컬 Codex 설정, `.venv`, 백업, 전송 파일, 콘솔 수집 파일, 로컬 테스트 코드와 도우미는 Git에서 제외됩니다.

API 근거: https://github.com/pterodactyl/panel/blob/1.0-develop/app/Http/Controllers/Api/Client/Servers/FileController.php
