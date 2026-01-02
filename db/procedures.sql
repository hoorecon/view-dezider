USE view_dezider;

DELIMITER $$

CREATE PROCEDURE sp_create_project(
  IN p_name VARCHAR(255),
  IN p_description TEXT,
  IN p_owner_id BIGINT
)
BEGIN
  INSERT INTO projects (name, description, owner_id)
  VALUES (p_name, p_description, p_owner_id);
  SELECT LAST_INSERT_ID() AS project_id;
END$$

CREATE PROCEDURE sp_add_factor_group(
  IN p_project_id BIGINT,
  IN p_code VARCHAR(10),
  IN p_name VARCHAR(255),
  IN p_weight DECIMAL(6,2)
)
BEGIN
  INSERT INTO factor_groups (project_id, code, name, weight)
  VALUES (p_project_id, p_code, p_name, p_weight);
  SELECT LAST_INSERT_ID() AS factor_group_id;
END$$

CREATE PROCEDURE sp_add_sub_factor(
  IN p_factor_group_id BIGINT,
  IN p_code VARCHAR(10),
  IN p_name VARCHAR(255),
  IN p_weight_percent DECIMAL(6,2)
)
BEGIN
  INSERT INTO sub_factors (factor_group_id, code, name, weight_percent)
  VALUES (p_factor_group_id, p_code, p_name, p_weight_percent);
  SELECT LAST_INSERT_ID() AS sub_factor_id;
END$$

CREATE PROCEDURE sp_add_gate(
  IN p_project_id BIGINT,
  IN p_factor_group_id BIGINT,
  IN p_gate_type ENUM('HARD','SOFT'),
  IN p_mode ENUM('PENALTY_POINTS','CAP_PERCENT','FLAG_ONLY'),
  IN p_threshold DECIMAL(6,2),
  IN p_penalty_points DECIMAL(6,2),
  IN p_cap_percent DECIMAL(6,2),
  IN p_note VARCHAR(255)
)
BEGIN
  INSERT INTO gates (project_id, factor_group_id, gate_type, mode, threshold, penalty_points, cap_percent, note)
  VALUES (p_project_id, p_factor_group_id, p_gate_type, p_mode, p_threshold, p_penalty_points, p_cap_percent, p_note);
  SELECT LAST_INSERT_ID() AS gate_id;
END$$

CREATE PROCEDURE sp_add_option(
  IN p_project_id BIGINT,
  IN p_name VARCHAR(255),
  IN p_description TEXT
)
BEGIN
  INSERT INTO options (project_id, name, description)
  VALUES (p_project_id, p_name, p_description);
  SELECT LAST_INSERT_ID() AS option_id;
END$$

CREATE PROCEDURE sp_set_score(
  IN p_option_id BIGINT,
  IN p_sub_factor_id BIGINT,
  IN p_score DECIMAL(4,2)
)
BEGIN
  INSERT INTO scores (option_id, sub_factor_id, score)
  VALUES (p_option_id, p_sub_factor_id, p_score)
  ON DUPLICATE KEY UPDATE score = VALUES(score);
END$$

CREATE PROCEDURE sp_compute_results(IN p_project_id BIGINT)
BEGIN
  DELETE FROM option_results WHERE project_id = p_project_id;

  INSERT INTO option_results (project_id, option_id, base_score, total_score, disqualified, flags)
  SELECT
    o.project_id,
    o.id AS option_id,
    IFNULL(SUM((s.score / 10) * (sf.weight_percent / 100) * fg.weight), 0) AS base_score,
    IFNULL(SUM((s.score / 10) * (sf.weight_percent / 100) * fg.weight), 0) AS total_score,
    0 AS disqualified,
    '' AS flags
  FROM options o
  LEFT JOIN scores s ON s.option_id = o.id
  LEFT JOIN sub_factors sf ON sf.id = s.sub_factor_id
  LEFT JOIN factor_groups fg ON fg.id = sf.factor_group_id
  WHERE o.project_id = p_project_id
  GROUP BY o.id;

  UPDATE option_results r
  JOIN (
    SELECT
      o.id AS option_id,
      COUNT(*) AS hard_fail_count
    FROM options o
    JOIN gates g ON g.project_id = o.project_id AND g.gate_type = 'HARD'
    JOIN factor_groups fg ON fg.id = g.factor_group_id
    LEFT JOIN sub_factors sf ON sf.factor_group_id = fg.id
    LEFT JOIN scores s ON s.sub_factor_id = sf.id AND s.option_id = o.id
    GROUP BY o.id, g.id
    HAVING AVG(IFNULL(s.score, 0)) < g.threshold
  ) hf ON hf.option_id = r.option_id
  SET r.disqualified = 1;

  UPDATE option_results r
  JOIN (
    SELECT
      o.id AS option_id,
      g.mode,
      g.threshold,
      g.penalty_points,
      g.cap_percent,
      g.note,
      AVG(IFNULL(s.score, 0)) AS avg_score
    FROM options o
    JOIN gates g ON g.project_id = o.project_id AND g.gate_type = 'SOFT'
    JOIN factor_groups fg ON fg.id = g.factor_group_id
    LEFT JOIN sub_factors sf ON sf.factor_group_id = fg.id
    LEFT JOIN scores s ON s.sub_factor_id = sf.id AND s.option_id = o.id
    WHERE o.project_id = p_project_id
    GROUP BY o.id, g.id
  ) sg ON sg.option_id = r.option_id
  SET
    r.total_score = CASE
      WHEN sg.avg_score < sg.threshold AND sg.mode = 'PENALTY_POINTS' THEN r.total_score - sg.penalty_points
      WHEN sg.avg_score < sg.threshold AND sg.mode = 'CAP_PERCENT' THEN LEAST(r.total_score, sg.cap_percent)
      ELSE r.total_score
    END,
    r.flags = CASE
      WHEN sg.avg_score < sg.threshold AND sg.mode = 'FLAG_ONLY' THEN CONCAT_WS(';', NULLIF(r.flags, ''), sg.note)
      ELSE r.flags
    END;

  SELECT * FROM option_results WHERE project_id = p_project_id ORDER BY disqualified, total_score DESC;
END$$

DELIMITER ;
