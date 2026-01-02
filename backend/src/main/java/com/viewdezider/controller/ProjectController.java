package com.viewdezider.controller;

import com.viewdezider.model.FactorGroupRequest;
import com.viewdezider.model.GateRequest;
import com.viewdezider.model.OptionRequest;
import com.viewdezider.model.ProjectRequest;
import com.viewdezider.model.SubFactorRequest;
import com.viewdezider.service.DecisionService;
import jakarta.validation.Valid;
import java.security.Principal;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/projects")
public class ProjectController {
  private final DecisionService decisionService;

  public ProjectController(DecisionService decisionService) {
    this.decisionService = decisionService;
  }

  @GetMapping
  public ResponseEntity<List<Map<String, Object>>> listProjects() {
    return ResponseEntity.ok(decisionService.listProjects());
  }

  @GetMapping("/{projectId}")
  public ResponseEntity<Map<String, Object>> getProject(@PathVariable long projectId) {
    return ResponseEntity.ok(decisionService.getProject(projectId));
  }

  @PostMapping
  public ResponseEntity<Map<String, Object>> createProject(@Valid @RequestBody ProjectRequest request,
                                                           Principal principal) {
    long projectId = decisionService.createProject(request.name(), request.description(), 1L);
    Map<String, Object> response = new HashMap<>();
    response.put("projectId", projectId);
    return ResponseEntity.ok(response);
  }

  @PostMapping("/{projectId}/factor-groups")
  public ResponseEntity<Map<String, Object>> addFactorGroup(@PathVariable long projectId,
                                                            @Valid @RequestBody FactorGroupRequest request) {
    long id = decisionService.addFactorGroup(projectId, request.code(), request.name(), request.weight());
    return ResponseEntity.ok(Map.of("factorGroupId", id));
  }

  @PostMapping("/factor-groups/{factorGroupId}/sub-factors")
  public ResponseEntity<Map<String, Object>> addSubFactor(@PathVariable long factorGroupId,
                                                          @Valid @RequestBody SubFactorRequest request) {
    long id = decisionService.addSubFactor(factorGroupId, request.code(), request.name(), request.weightPercent());
    return ResponseEntity.ok(Map.of("subFactorId", id));
  }

  @PostMapping("/{projectId}/gates")
  public ResponseEntity<Map<String, Object>> addGate(@PathVariable long projectId,
                                                     @Valid @RequestBody GateRequest request) {
    long id = decisionService.addGate(projectId, request.factorGroupId(), request.gateType(), request.mode(),
        request.threshold(),
        request.penaltyPoints() == null ? 0 : request.penaltyPoints(),
        request.capPercent() == null ? 0 : request.capPercent(),
        request.note());
    return ResponseEntity.ok(Map.of("gateId", id));
  }

  @PostMapping("/{projectId}/options")
  public ResponseEntity<Map<String, Object>> addOption(@PathVariable long projectId,
                                                       @Valid @RequestBody OptionRequest request) {
    long id = decisionService.addOption(projectId, request.name(), request.description());
    return ResponseEntity.ok(Map.of("optionId", id));
  }
}
