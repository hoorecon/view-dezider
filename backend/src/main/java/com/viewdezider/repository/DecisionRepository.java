package com.viewdezider.repository;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import javax.sql.DataSource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.simple.SimpleJdbcCall;
import org.springframework.stereotype.Repository;

@Repository
public class DecisionRepository {
  private final JdbcTemplate jdbcTemplate;
  private final SimpleJdbcCall createProjectCall;
  private final SimpleJdbcCall addFactorGroupCall;
  private final SimpleJdbcCall addSubFactorCall;
  private final SimpleJdbcCall addGateCall;
  private final SimpleJdbcCall addOptionCall;
  private final SimpleJdbcCall setScoreCall;
  private final SimpleJdbcCall computeResultsCall;

  public DecisionRepository(DataSource dataSource, JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
    this.createProjectCall = new SimpleJdbcCall(dataSource).withProcedureName("sp_create_project");
    this.addFactorGroupCall = new SimpleJdbcCall(dataSource).withProcedureName("sp_add_factor_group");
    this.addSubFactorCall = new SimpleJdbcCall(dataSource).withProcedureName("sp_add_sub_factor");
    this.addGateCall = new SimpleJdbcCall(dataSource).withProcedureName("sp_add_gate");
    this.addOptionCall = new SimpleJdbcCall(dataSource).withProcedureName("sp_add_option");
    this.setScoreCall = new SimpleJdbcCall(dataSource).withProcedureName("sp_set_score");
    this.computeResultsCall = new SimpleJdbcCall(dataSource).withProcedureName("sp_compute_results");
  }

  public long createProject(String name, String description, long ownerId) {
    Map<String, Object> params = new HashMap<>();
    params.put("p_name", name);
    params.put("p_description", description);
    params.put("p_owner_id", ownerId);
    Map<String, Object> result = createProjectCall.execute(params);
    return ((Number) result.get("project_id")).longValue();
  }

  public long addFactorGroup(long projectId, String code, String name, double weight) {
    Map<String, Object> params = new HashMap<>();
    params.put("p_project_id", projectId);
    params.put("p_code", code);
    params.put("p_name", name);
    params.put("p_weight", weight);
    Map<String, Object> result = addFactorGroupCall.execute(params);
    return ((Number) result.get("factor_group_id")).longValue();
  }

  public long addSubFactor(long factorGroupId, String code, String name, double weightPercent) {
    Map<String, Object> params = new HashMap<>();
    params.put("p_factor_group_id", factorGroupId);
    params.put("p_code", code);
    params.put("p_name", name);
    params.put("p_weight_percent", weightPercent);
    Map<String, Object> result = addSubFactorCall.execute(params);
    return ((Number) result.get("sub_factor_id")).longValue();
  }

  public long addGate(long projectId, long factorGroupId, String gateType, String mode,
                      double threshold, double penaltyPoints, double capPercent, String note) {
    Map<String, Object> params = new HashMap<>();
    params.put("p_project_id", projectId);
    params.put("p_factor_group_id", factorGroupId);
    params.put("p_gate_type", gateType);
    params.put("p_mode", mode);
    params.put("p_threshold", threshold);
    params.put("p_penalty_points", penaltyPoints);
    params.put("p_cap_percent", capPercent);
    params.put("p_note", note);
    Map<String, Object> result = addGateCall.execute(params);
    return ((Number) result.get("gate_id")).longValue();
  }

  public long addOption(long projectId, String name, String description) {
    Map<String, Object> params = new HashMap<>();
    params.put("p_project_id", projectId);
    params.put("p_name", name);
    params.put("p_description", description);
    Map<String, Object> result = addOptionCall.execute(params);
    return ((Number) result.get("option_id")).longValue();
  }

  public void setScore(long optionId, long subFactorId, double score) {
    Map<String, Object> params = new HashMap<>();
    params.put("p_option_id", optionId);
    params.put("p_sub_factor_id", subFactorId);
    params.put("p_score", score);
    setScoreCall.execute(params);
  }

  public List<Map<String, Object>> computeResults(long projectId) {
    Map<String, Object> params = new HashMap<>();
    params.put("p_project_id", projectId);
    Map<String, Object> result = computeResultsCall.execute(params);
    return (List<Map<String, Object>>) result.get("#result-set-1");
  }

  public List<Map<String, Object>> listProjects() {
    return jdbcTemplate.queryForList("SELECT * FROM projects ORDER BY created_at DESC");
  }

  public Map<String, Object> getProject(long projectId) {
    return jdbcTemplate.queryForMap("SELECT * FROM projects WHERE id = ?", projectId);
  }

  public void logAudit(long projectId, Long actorId, String action, String details) {
    jdbcTemplate.update("INSERT INTO audit_log (project_id, actor_id, action, details) VALUES (?, ?, ?, ?)",
        projectId, actorId, action, details);
  }
}
