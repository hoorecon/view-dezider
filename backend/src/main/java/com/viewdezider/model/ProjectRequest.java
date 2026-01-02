package com.viewdezider.model;

import jakarta.validation.constraints.NotBlank;

public record ProjectRequest(
    @NotBlank String name,
    String description
) {}
