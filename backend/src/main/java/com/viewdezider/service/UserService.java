package com.viewdezider.service;

import com.viewdezider.repository.UserRepository;
import com.viewdezider.security.JwtService;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
public class UserService {
  private final UserRepository userRepository;
  private final PasswordEncoder passwordEncoder;
  private final JwtService jwtService;

  public UserService(UserRepository userRepository, PasswordEncoder passwordEncoder, JwtService jwtService) {
    this.userRepository = userRepository;
    this.passwordEncoder = passwordEncoder;
    this.jwtService = jwtService;
  }

  public String register(String email, String password, String role) {
    String normalizedRole = role == null ? "MEMBER" : role.toUpperCase();
    String hash = passwordEncoder.encode(password);
    userRepository.createUser(email, hash, normalizedRole);
    return jwtService.generateToken(email, normalizedRole);
  }

  public String login(String email, String password) {
    UserRepository.UserRecord user = userRepository.findByEmail(email)
        .orElseThrow(() -> new IllegalArgumentException("Invalid credentials"));
    if (!passwordEncoder.matches(password, user.passwordHash())) {
      throw new IllegalArgumentException("Invalid credentials");
    }
    return jwtService.generateToken(user.email(), user.role());
  }
}
