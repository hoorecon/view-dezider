package com.viewdezider.model;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

public record ScoreRequest(
    @NotNull Long subFactorId,
    @NotNull @Min(0) @Max(10) Double score
) {}
