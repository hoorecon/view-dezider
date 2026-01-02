package com.viewdezider.controller;

import com.viewdezider.service.DecisionService;
import java.util.List;
import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/projects")
public class ResultController {
  private final DecisionService decisionService;

  public ResultController(DecisionService decisionService) {
    this.decisionService = decisionService;
  }

  @PostMapping("/{projectId}/compute")
  public ResponseEntity<List<Map<String, Object>>> compute(@PathVariable long projectId) {
    return ResponseEntity.ok(decisionService.computeResults(projectId));
  }

  @GetMapping("/{projectId}/export")
  public ResponseEntity<List<Map<String, Object>>> export(@PathVariable long projectId) {
    return ResponseEntity.ok(decisionService.computeResults(projectId));
  }
}
