-- DB와 계정 생성
CREATE DATABASE IF NOT EXISTS minwon_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

USE minwon_db;

CREATE USER IF NOT EXISTS 'minwon_user'@'%' IDENTIFIED BY 'dhsmfdkssud567810';
GRANT ALL PRIVILEGES ON minwon_db.* TO 'minwon_user'@'%';
FLUSH PRIVILEGES;

-- 1) 민원세션
CREATE TABLE IF NOT EXISTS minwon_session (
    session_id    CHAR(36)     NOT NULL,
    received_at   DATETIME     NOT NULL,
    text_raw      TEXT         NOT NULL,
    minwon_type   VARCHAR(20)  NOT NULL,
    risk_level    VARCHAR(10)  NOT NULL,
    handling_type VARCHAR(20)  NOT NULL,
    status        VARCHAR(20)  NOT NULL,
    PRIMARY KEY (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2) 엔진로그
CREATE TABLE IF NOT EXISTS engine_log (
    log_id        BIGINT       NOT NULL AUTO_INCREMENT,
    session_id    CHAR(36)     NOT NULL,
    stage         VARCHAR(20)  NOT NULL,
    request_text  TEXT         NOT NULL,
    response_json JSON         NOT NULL,
    created_at    DATETIME     NOT NULL,
    PRIMARY KEY (log_id),
    CONSTRAINT fk_engine_log_session
      FOREIGN KEY (session_id) REFERENCES minwon_session(session_id)
      ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3) 문자안내
CREATE TABLE IF NOT EXISTS sms_info (
    sms_id       BIGINT      NOT NULL AUTO_INCREMENT,
    session_id   CHAR(36)    NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    masked_phone VARCHAR(20) NOT NULL,
    agree_sms    TINYINT(1)  NOT NULL,
    created_at   DATETIME    NOT NULL,
    PRIMARY KEY (sms_id),
    CONSTRAINT fk_sms_session
      FOREIGN KEY (session_id) REFERENCES minwon_session(session_id)
      ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4) 민원티켓
CREATE TABLE IF NOT EXISTS ticket (
    ticket_id   BIGINT      NOT NULL AUTO_INCREMENT,
    session_id  CHAR(36)    NOT NULL,
    category    VARCHAR(50) NOT NULL,
    risk_level  VARCHAR(10) NOT NULL,
    status      VARCHAR(20) NOT NULL,
    dept_name   VARCHAR(100) NOT NULL,
    created_at  DATETIME    NOT NULL,
    resolved_at DATETIME    NULL,
    PRIMARY KEY (ticket_id),
    CONSTRAINT fk_ticket_session
      FOREIGN KEY (session_id) REFERENCES minwon_session(session_id)
      ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
