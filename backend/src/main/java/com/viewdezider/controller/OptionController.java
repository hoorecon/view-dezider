package com.viewdezider.controller;

import com.viewdezider.model.ScoreRequest;
import com.viewdezider.service.DecisionService;
import jakarta.validation.Valid;
import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/options")
public class OptionController {
  private final DecisionService decisionService;

  public OptionController(DecisionService decisionService) {
    this.decisionService = decisionService;
  }

  @PostMapping("/{optionId}/scores")
  public ResponseEntity<Map<String, Object>> setScore(@PathVariable long optionId,
                                                      @Valid @RequestBody ScoreRequest request) {
    decisionService.setScore(optionId, request.subFactorId(), request.score());
    return ResponseEntity.ok(Map.of("status", "ok"));
  }
}
