CREATE DATABASE IF NOT EXISTS view_dezider;
USE view_dezider;

CREATE TABLE IF NOT EXISTS users (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('ADMIN','MEMBER') NOT NULL DEFAULT 'MEMBER',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  owner_id BIGINT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (owner_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS factor_groups (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  project_id BIGINT NOT NULL,
  code VARCHAR(10) NOT NULL,
  name VARCHAR(255) NOT NULL,
  weight DECIMAL(6,2) NOT NULL,
  UNIQUE KEY uq_factor_group (project_id, code),
  FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS sub_factors (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  factor_group_id BIGINT NOT NULL,
  code VARCHAR(10) NOT NULL,
  name VARCHAR(255) NOT NULL,
  weight_percent DECIMAL(6,2) NOT NULL,
  UNIQUE KEY uq_sub_factor (factor_group_id, code),
  FOREIGN KEY (factor_group_id) REFERENCES factor_groups(id)
);

CREATE TABLE IF NOT EXISTS gates (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  project_id BIGINT NOT NULL,
  factor_group_id BIGINT NOT NULL,
  gate_type ENUM('HARD','SOFT') NOT NULL,
  mode ENUM('PENALTY_POINTS','CAP_PERCENT','FLAG_ONLY') NOT NULL,
  threshold DECIMAL(6,2) NOT NULL,
  penalty_points DECIMAL(6,2) DEFAULT 0,
  cap_percent DECIMAL(6,2) DEFAULT 0,
  note VARCHAR(255),
  FOREIGN KEY (project_id) REFERENCES projects(id),
  FOREIGN KEY (factor_group_id) REFERENCES factor_groups(id)
);

CREATE TABLE IF NOT EXISTS options (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  project_id BIGINT NOT NULL,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS scores (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  option_id BIGINT NOT NULL,
  sub_factor_id BIGINT NOT NULL,
  score DECIMAL(4,2) NOT NULL,
  UNIQUE KEY uq_score (option_id, sub_factor_id),
  FOREIGN KEY (option_id) REFERENCES options(id),
  FOREIGN KEY (sub_factor_id) REFERENCES sub_factors(id)
);

CREATE TABLE IF NOT EXISTS option_results (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  project_id BIGINT NOT NULL,
  option_id BIGINT NOT NULL,
  base_score DECIMAL(10,2) NOT NULL,
  total_score DECIMAL(10,2) NOT NULL,
  disqualified TINYINT(1) NOT NULL DEFAULT 0,
  flags TEXT,
  computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_option_result (project_id, option_id),
  FOREIGN KEY (project_id) REFERENCES projects(id),
  FOREIGN KEY (option_id) REFERENCES options(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  project_id BIGINT NOT NULL,
  actor_id BIGINT,
  action VARCHAR(255) NOT NULL,
  details TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (project_id) REFERENCES projects(id),
  FOREIGN KEY (actor_id) REFERENCES users(id)
);
