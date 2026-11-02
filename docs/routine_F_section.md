# 예약 작업 프롬프트에 덧붙일 F 섹션

> 전제: 이 단계가 동작하려면 예약 작업 실행 세션이 JNNKYNG/vb-feed-7k2m 에 push 권한을 가져야 함.
> (2026-11-02 테스트: create_trigger로 만든 작업에는 리포 권한이 넘어가지 않음 → claude.ai 예약 작업 설정에서 리포를 붙여야 함)

## 저녁용

══════════ F. 팟캐스트 피드 갱신 ══════════

C에서 만든 mp3가 있을 때만 실행(오디오가 없으면 이 단계 생략). 클라우드 셸에서:
gh auth setup-git 2>/dev/null; git clone --depth 1 https://github.com/JNNKYNG/vb-feed-7k2m feedrepo
(clone·push가 권한 오류면 add_repo(owner="JNNKYNG", repo="vb-feed-7k2m", access="push")를 한 번 호출한 뒤 다시 시도)
python3 feedrepo/scripts/add_episode.py --file briefing_YYYY-MM-DD.mp3 --id YYYY-MM-DD-pm --title '[저녁] M/D(요일) headline' --desc 'analysis 1)의 핵심 논지를 평문 3문장 + " 분석·관찰이며 투자 권유가 아님."' --seconds <ffprobe duration>
스크립트가 push 실패 시 pull --rebase 후 1회 재시도함. 종료코드가 0이 아니면 나머지는 그대로 진행하고 알림에 "피드 갱신 실패(사유)"를 추가.

## 아침용

══════════ F. 팟캐스트 피드 갱신 ══════════

위와 동일하되 --file briefing_YYYY-MM-DD-am.mp3 --id YYYY-MM-DD-am --title '[아침] M/D(요일) headline'.
