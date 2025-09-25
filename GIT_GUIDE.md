# 📚 Git 버전 관리 가이드

## 🚀 기본 명령어

### 상태 확인
```bash
# 현재 상태 확인
git status

# 변경사항 요약
git diff

# 커밋 히스토리
git log --oneline
```

### 커밋 관리
```bash
# 변경사항 스테이징
git add .                    # 모든 변경사항
git add <파일명>             # 특정 파일만

# 커밋
git commit -m "커밋 메시지"

# 마지막 커밋 수정
git commit --amend -m "수정된 메시지"
```

### 브랜치 관리
```bash
# 브랜치 목록
git branch

# 새 브랜치 생성
git branch <브랜치명>

# 브랜치 전환
git checkout <브랜치명>

# 브랜치 생성 및 전환
git checkout -b <브랜치명>

# 브랜치 삭제
git branch -d <브랜치명>
```

## 🔄 워크플로우

### 1. 개발 시작
```bash
# 최신 상태로 업데이트
git pull origin main

# 새 기능 브랜치 생성
git checkout -b feature/새기능명
```

### 2. 개발 중
```bash
# 변경사항 확인
git status
git diff

# 변경사항 스테이징
git add .

# 커밋
git commit -m "기능: 새 기능 구현"
```

### 3. 개발 완료
```bash
# 메인 브랜치로 전환
git checkout main

# 브랜치 병합
git merge feature/새기능명

# 브랜치 삭제
git branch -d feature/새기능명
```

## 📝 커밋 메시지 규칙

### 형식
```
<타입>: <제목>

<본문>

<푸터>
```

### 타입
- `feat`: 새로운 기능
- `fix`: 버그 수정
- `docs`: 문서 수정
- `style`: 코드 스타일 변경
- `refactor`: 리팩토링
- `test`: 테스트 추가/수정
- `chore`: 빌드, 설정 등

### 예시
```bash
git commit -m "feat: 2D 분할 기능 추가"
git commit -m "fix: 이미지 회전 버그 수정"
git commit -m "docs: README 업데이트"
```

## 🔧 유용한 명령어

### 되돌리기
```bash
# 마지막 커밋 취소 (변경사항 유지)
git reset --soft HEAD~1

# 마지막 커밋 완전 삭제
git reset --hard HEAD~1

# 특정 파일만 되돌리기
git checkout HEAD -- <파일명>
```

### 히스토리 관리
```bash
# 커밋 히스토리 그래프
git log --graph --oneline --all

# 특정 파일 히스토리
git log --follow <파일명>

# 커밋 상세 정보
git show <커밋해시>
```

### 임시 저장
```bash
# 작업 임시 저장
git stash

# 임시 저장 목록
git stash list

# 임시 저장 복원
git stash pop

# 임시 저장 삭제
git stash drop
```

## 🌐 원격 저장소

### GitHub 연동
```bash
# 원격 저장소 추가
git remote add origin <저장소URL>

# 원격 저장소 확인
git remote -v

# 원격으로 푸시
git push -u origin main

# 원격에서 풀
git pull origin main
```

### 브랜치 푸시
```bash
# 새 브랜치 푸시
git push -u origin <브랜치명>

# 모든 브랜치 푸시
git push --all origin
```

## 🚨 주의사항

### 절대 하지 말 것
- `git reset --hard` (신중하게 사용)
- `git push --force` (팀 작업 시)
- 커밋 메시지 없이 커밋

### 권장사항
- 작은 단위로 자주 커밋
- 의미있는 커밋 메시지 작성
- 브랜치를 활용한 기능 개발
- 정기적으로 원격 저장소와 동기화

## 📋 일일 체크리스트

```bash
# 1. 상태 확인
git status

# 2. 변경사항 확인
git diff

# 3. 커밋
git add .
git commit -m "작업 내용"

# 4. 원격 동기화
git push origin main
```
