package com.squinchmods.vegetate.common.vegetate.ui.model;

import java.util.Objects;

public record ConfigUiEntryId(String value) {
  public ConfigUiEntryId {
    Objects.requireNonNull(value, "value cannot be null");

    if (value.isBlank()) {
      throw new IllegalArgumentException("value cannot be blank");
    }
  }
}
