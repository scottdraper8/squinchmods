package com.squinchmods.treeify.common.treeify.ui.model;

import java.util.List;
import java.util.Objects;
import java.util.Optional;
import net.minecraft.network.chat.Component;

public record ConfigUiCategoryView(
	String id,
	Component title,
	Optional<Component> description,
	List<ConfigUiEntryView> entries
)
{
	public ConfigUiCategoryView {
		Objects.requireNonNull(id, "id cannot be null");

		if (id.isBlank()) {
			throw new IllegalArgumentException("id cannot be blank");
		}

		Objects.requireNonNull(title, "title cannot be null");
		description = Objects.requireNonNull(description, "description cannot be null");
		entries = List.copyOf(entries);
	}
}
