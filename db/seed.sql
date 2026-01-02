USE view_dezider;

INSERT INTO users (email, password_hash, role) VALUES
  ('admin@viewdezider.local', '$2a$10$wXW4ukN9hLa1g9/6v1N6bO7vXjKX8qAT7/kYQ/DbkX1W3SIX5dBfK', 'ADMIN');

CALL sp_create_project('LMS Purchase', 'Evaluate LMS vendor options', 1);
SET @project_id = LAST_INSERT_ID();

CALL sp_add_factor_group(@project_id, 'A1', 'Strategy Fit', 85);
SET @a1 = LAST_INSERT_ID();
CALL sp_add_factor_group(@project_id, 'A2', 'Total Cost', 67.5);
SET @a2 = LAST_INSERT_ID();
CALL sp_add_factor_group(@project_id, 'A3', 'Compliance', 52.5);
SET @a3 = LAST_INSERT_ID();
CALL sp_add_factor_group(@project_id, 'A4', 'Vendor Stability', 40);
SET @a4 = LAST_INSERT_ID();
CALL sp_add_factor_group(@project_id, 'B1', 'Implementation', 32.5);
SET @b1 = LAST_INSERT_ID();
CALL sp_add_factor_group(@project_id, 'B2', 'Support', 25);
SET @b2 = LAST_INSERT_ID();
CALL sp_add_factor_group(@project_id, 'B3', 'UX', 15);
SET @b3 = LAST_INSERT_ID();
CALL sp_add_factor_group(@project_id, 'B4', 'Reporting', 10);
SET @b4 = LAST_INSERT_ID();

CALL sp_add_sub_factor(@a1, '1.1', 'Strategic alignment', 100);
CALL sp_add_sub_factor(@a2, '2.1', 'Licensing costs', 100);
CALL sp_add_sub_factor(@a3, '3.1', 'Security posture', 100);
CALL sp_add_sub_factor(@a4, '4.1', 'Financial stability', 100);
CALL sp_add_sub_factor(@b1, '5.1', 'Implementation effort', 100);
CALL sp_add_sub_factor(@b2, '6.1', 'Support response', 100);
CALL sp_add_sub_factor(@b3, '7.1', 'User experience', 100);
CALL sp_add_sub_factor(@b4, '8.1', 'Analytics depth', 100);

CALL sp_add_gate(@project_id, @a3, 'HARD', 'FLAG_ONLY', 6, 0, 0, 'Security minimum');
CALL sp_add_gate(@project_id, @b1, 'SOFT', 'PENALTY_POINTS', 5, 10, 0, 'Implementation complexity');
CALL sp_add_gate(@project_id, @b4, 'SOFT', 'CAP_PERCENT', 6, 0, 60, 'Reporting cap');

CALL sp_add_option(@project_id, 'Vendor Alpha', 'Cloud-first LMS');
SET @opt1 = LAST_INSERT_ID();
CALL sp_add_option(@project_id, 'Vendor Beta', 'On-premises LMS');
SET @opt2 = LAST_INSERT_ID();

SET @sf = (SELECT id FROM sub_factors WHERE code = '1.1' AND factor_group_id = @a1);
CALL sp_set_score(@opt1, @sf, 8);
CALL sp_set_score(@opt2, @sf, 6);
SET @sf = (SELECT id FROM sub_factors WHERE code = '2.1' AND factor_group_id = @a2);
CALL sp_set_score(@opt1, @sf, 7);
CALL sp_set_score(@opt2, @sf, 8);
SET @sf = (SELECT id FROM sub_factors WHERE code = '3.1' AND factor_group_id = @a3);
CALL sp_set_score(@opt1, @sf, 4);
CALL sp_set_score(@opt2, @sf, 7);
SET @sf = (SELECT id FROM sub_factors WHERE code = '4.1' AND factor_group_id = @a4);
CALL sp_set_score(@opt1, @sf, 7);
CALL sp_set_score(@opt2, @sf, 6);
SET @sf = (SELECT id FROM sub_factors WHERE code = '5.1' AND factor_group_id = @b1);
CALL sp_set_score(@opt1, @sf, 4);
CALL sp_set_score(@opt2, @sf, 6);
SET @sf = (SELECT id FROM sub_factors WHERE code = '6.1' AND factor_group_id = @b2);
CALL sp_set_score(@opt1, @sf, 6);
CALL sp_set_score(@opt2, @sf, 7);
SET @sf = (SELECT id FROM sub_factors WHERE code = '7.1' AND factor_group_id = @b3);
CALL sp_set_score(@opt1, @sf, 7);
CALL sp_set_score(@opt2, @sf, 7);
SET @sf = (SELECT id FROM sub_factors WHERE code = '8.1' AND factor_group_id = @b4);
CALL sp_set_score(@opt1, @sf, 5);
CALL sp_set_score(@opt2, @sf, 8);

CALL sp_compute_results(@project_id);
