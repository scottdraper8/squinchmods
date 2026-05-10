package com.squinchmods.vegetate.common.vegetate.ui.model;

import java.util.List;
import java.util.Objects;
import java.util.Optional;
import net.minecraft.network.chat.Component;

public record ConfigUiCategoryView(
    String id, Component title, Optional<Component> description, List<ConfigUiEntryView> entries) {
  public ConfigUiCategoryView(
      String id,
      Component title,
      Optional<Component> description,
      List<ConfigUiEntryView> entries) {
    Objects.requireNonNull(id, "id cannot be null");
    if (id.isBlank()) {
      throw new IllegalArgumentException("id cannot be blank");
    }
    Objects.requireNonNull(title, "title cannot be null");
    Objects.requireNonNull(description, "description cannot be null");
    this.id = id;
    this.title = title;
    this.description = description;
    this.entries = List.copyOf(entries);
  }
}
