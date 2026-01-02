package com.viewdezider.repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

@Repository
public class UserRepository {
  private final JdbcTemplate jdbcTemplate;

  public UserRepository(JdbcTemplate jdbcTemplate) {
    this.jdbcTemplate = jdbcTemplate;
  }

  public Optional<UserRecord> findByEmail(String email) {
    return jdbcTemplate.query("SELECT id, email, password_hash, role FROM users WHERE email = ?",
            new UserRowMapper(), email)
        .stream().findFirst();
  }

  public long createUser(String email, String passwordHash, String role) {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
        email, passwordHash, role);
    return jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
  }

  public record UserRecord(long id, String email, String passwordHash, String role) {}

  private static class UserRowMapper implements RowMapper<UserRecord> {
    @Override
    public UserRecord mapRow(ResultSet rs, int rowNum) throws SQLException {
      return new UserRecord(
          rs.getLong("id"),
          rs.getString("email"),
          rs.getString("password_hash"),
          rs.getString("role")
      );
    }
  }
}
