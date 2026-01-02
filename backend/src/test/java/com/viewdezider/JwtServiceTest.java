package com.viewdezider;

import com.viewdezider.security.JwtService;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

public class JwtServiceTest {
  @Test
  void generatesTokenWithSubject() {
    JwtService jwtService = new JwtService("test-secret-test-secret-test-secret", 10);
    String token = jwtService.generateToken("user@example.com", "MEMBER");
    String email = jwtService.extractEmail(token);
    assertThat(email).isEqualTo("user@example.com");
  }
}
