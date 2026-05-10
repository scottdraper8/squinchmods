package com.squinchmods.vegetate.common.vegetate.ui.service;

import java.util.Objects;
import java.util.Optional;
import net.minecraft.network.chat.Component;

public record ConfigUiApplyResult(
	boolean successful,
	Optional<Component> message
)
{
	public ConfigUiApplyResult {
		message = Objects.requireNonNull(message, "message cannot be null");
	}

	public static ConfigUiApplyResult success() {
		return new ConfigUiApplyResult(true, Optional.empty());
	}

	public static ConfigUiApplyResult success(Component message) {
		return new ConfigUiApplyResult(true, Optional.of(message));
	}

	public static ConfigUiApplyResult failure(Component message) {
		return new ConfigUiApplyResult(false, Optional.of(message));
	}
}
