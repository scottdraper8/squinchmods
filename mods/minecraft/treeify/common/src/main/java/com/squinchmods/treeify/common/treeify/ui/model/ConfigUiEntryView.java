package com.squinchmods.treeify.common.treeify.ui.model;

import java.util.Objects;
import java.util.Optional;
import net.minecraft.network.chat.Component;

public record ConfigUiEntryView(
	ConfigUiEntryId id,
	Component title,
	Optional<Component> description,
	boolean defaultEnabled,
	ConfigUiEntrySupport support,
	Optional<ConfigUiDetailRoute> detailRoute
)
{
	public ConfigUiEntryView {
		Objects.requireNonNull(id, "id cannot be null");
		Objects.requireNonNull(title, "title cannot be null");
		description = Objects.requireNonNull(description, "description cannot be null");
		Objects.requireNonNull(support, "support cannot be null");
		detailRoute = Objects.requireNonNull(detailRoute, "detailRoute cannot be null");
	}
}
