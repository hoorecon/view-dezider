package com.viewdezider.security;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.SignatureAlgorithm;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.security.Key;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class JwtService {
  private final Key key;
  private final long expirationMinutes;

  public JwtService(@Value("${jwt.secret}") String secret,
                    @Value("${jwt.expirationMinutes}") long expirationMinutes) {
    this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
    this.expirationMinutes = expirationMinutes;
  }

  public String generateToken(String email, String role) {
    Instant now = Instant.now();
    return Jwts.builder()
        .setSubject(email)
        .claim("role", role)
        .setIssuedAt(Date.from(now))
        .setExpiration(Date.from(now.plus(expirationMinutes, ChronoUnit.MINUTES)))
        .signWith(key, SignatureAlgorithm.HS256)
        .compact();
  }

  public String extractEmail(String token) {
    return Jwts.parserBuilder().setSigningKey(key).build()
        .parseClaimsJws(token).getBody().getSubject();
  }
}
