package com.squinchmods.treeify.common.treeify.ui.service;

import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;

import java.util.Optional;

public record BiomeChoice(
	String id,
	Component displayName,
	Optional<Identifier> previewImage
)
{
	public BiomeChoice {
		previewImage = previewImage == null ? Optional.empty() : previewImage;
	}
}
