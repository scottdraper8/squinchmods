package com.squinchmods.vegetate.common.vegetate.ui.model;

import java.util.Objects;
import java.util.Optional;
import net.minecraft.network.chat.Component;

public record ConfigUiEntryView(
	ConfigUiEntryId id,
	Component title,
	Optional<Component> description,
	boolean defaultEnabled
)
{
	public ConfigUiEntryView {
		Objects.requireNonNull(id, "id cannot be null");
		Objects.requireNonNull(title, "title cannot be null");
		description = Objects.requireNonNull(description, "description cannot be null");
	}
}
