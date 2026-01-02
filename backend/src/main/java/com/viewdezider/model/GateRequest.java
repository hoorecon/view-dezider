package com.viewdezider.model;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record GateRequest(
    @NotNull Long factorGroupId,
    @NotBlank String gateType,
    @NotBlank String mode,
    @NotNull Double threshold,
    Double penaltyPoints,
    Double capPercent,
    String note
) {}
