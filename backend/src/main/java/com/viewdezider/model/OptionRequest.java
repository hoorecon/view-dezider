package com.viewdezider.model;

import jakarta.validation.constraints.NotBlank;

public record OptionRequest(
    @NotBlank String name,
    String description
) {}
