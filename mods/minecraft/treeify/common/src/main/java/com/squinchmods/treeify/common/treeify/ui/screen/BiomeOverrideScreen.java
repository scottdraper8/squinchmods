package com.squinchmods.treeify.common.treeify.ui.screen;

import com.squinchmods.treeify.common.treeify.ui.service.ConfigUiEditService;
import net.minecraft.network.chat.Component;

/**
 * Placeholder for the biome override screen.
 */
public class BiomeOverrideScreen {

    private final ConfigUiEditService editService;

    public BiomeOverrideScreen(ConfigUiEditService editService) {
        this.editService = editService;
    }

    public Component getTitle() {
        return Component.translatable("treeify.gui.screen.biome_overrides");
    }
}
