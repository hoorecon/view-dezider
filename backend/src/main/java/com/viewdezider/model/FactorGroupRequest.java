package com.viewdezider.model;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record FactorGroupRequest(
    @NotBlank String code,
    @NotBlank String name,
    @NotNull Double weight
) {}
