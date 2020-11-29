## 무인주차시스템 서버
---

- FLASK로 작성된 API서버입니다.

- ZAPPA를 사용하여 AWS LAMBDA에 배포되어있습니다.

- MYSQL DB를 사용합니다.

- JWT를 사용하여 사용자의 권한을 인가합니다.

- URI
    - /users : 사용자 정보를 조회합니다.
    - /parks : 주차장 정보를 조회합니다.
    - /favoriteparks : 즟겨찾기 주차장 정보를 조회합니다.
    - /booking : 예약 정보를 조회합니다.
