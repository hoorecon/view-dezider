package com.viewdezider.service;

import com.viewdezider.repository.DecisionRepository;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;

@Service
public class DecisionService {
  private final DecisionRepository repository;

  public DecisionService(DecisionRepository repository) {
    this.repository = repository;
  }

  public long createProject(String name, String description, long ownerId) {
    long projectId = repository.createProject(name, description, ownerId);
    repository.logAudit(projectId, ownerId, "PROJECT_CREATED", name);
    return projectId;
  }

  public List<Map<String, Object>> listProjects() {
    return repository.listProjects();
  }

  public Map<String, Object> getProject(long projectId) {
    return repository.getProject(projectId);
  }

  public long addFactorGroup(long projectId, String code, String name, double weight) {
    long id = repository.addFactorGroup(projectId, code, name, weight);
    repository.logAudit(projectId, null, "FACTOR_GROUP_ADDED", code);
    return id;
  }

  public long addSubFactor(long factorGroupId, String code, String name, double weightPercent) {
    long id = repository.addSubFactor(factorGroupId, code, name, weightPercent);
    return id;
  }

  public long addGate(long projectId, long factorGroupId, String gateType, String mode,
                      double threshold, double penaltyPoints, double capPercent, String note) {
    return repository.addGate(projectId, factorGroupId, gateType, mode, threshold,
        penaltyPoints, capPercent, note);
  }

  public long addOption(long projectId, String name, String description) {
    return repository.addOption(projectId, name, description);
  }

  public void setScore(long optionId, long subFactorId, double score) {
    repository.setScore(optionId, subFactorId, score);
  }

  public List<Map<String, Object>> computeResults(long projectId) {
    return repository.computeResults(projectId);
  }
}
