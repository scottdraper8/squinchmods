package com.squinchmods.vegetate.common.vegetate.ui.model;

import java.util.List;
import java.util.Objects;
import java.util.Optional;
import net.minecraft.network.chat.Component;

public record ConfigUiCatalogSnapshot(
	Component title,
	List<ConfigUiCategoryView> categories,
	Optional<Component> supportSummary
)
{
	public ConfigUiCatalogSnapshot {
		Objects.requireNonNull(title, "title cannot be null");
		categories = List.copyOf(categories);
		supportSummary = Objects.requireNonNull(supportSummary, "supportSummary cannot be null");
	}
}
