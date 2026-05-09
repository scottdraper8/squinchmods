package com.squinchmods.treeify.common.treeify.ui.model;

import java.util.Objects;
import java.util.Optional;
import net.minecraft.network.chat.Component;

public record ConfigUiDetailRoute(
	ConfigUiEntryId entryId,
	Optional<Component> title
)
{
	public ConfigUiDetailRoute {
		Objects.requireNonNull(entryId, "entryId cannot be null");
		title = Objects.requireNonNull(title, "title cannot be null");
	}

	public ConfigUiDetailRoute(ConfigUiEntryId entryId) {
		this(entryId, Optional.empty());
	}
}
