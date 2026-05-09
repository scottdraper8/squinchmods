package com.squinchmods.treeify.common.treeify.ui.screen;

import com.squinchmods.treeify.common.treeify.ui.model.ConfigUiDetailRoute;
import com.squinchmods.treeify.common.treeify.ui.service.ConfigUiEditService;
import com.squinchmods.treeify.common.treeify.ui.shell.TreeifyConfigScreenContext;
import dev.isxander.yacl3.api.ConfigCategory;
import dev.isxander.yacl3.api.Option;
import dev.isxander.yacl3.api.OptionGroup;
import dev.isxander.yacl3.api.YetAnotherConfigLib;
import dev.isxander.yacl3.api.controller.BooleanControllerBuilder;
import dev.isxander.yacl3.api.controller.FloatSliderControllerBuilder;
import dev.isxander.yacl3.api.controller.IntegerFieldControllerBuilder;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;

public class FeatureDetailScreen {

    private final ConfigUiDetailRoute route;
    private final TreeifyConfigScreenContext context;

    public FeatureDetailScreen(ConfigUiDetailRoute route, TreeifyConfigScreenContext context) {
        this.route = route;
        this.context = context;
    }

    public Screen generateScreen(Screen parent) {
        var entryId = route.entryId();
        // Since we don't have the full view passed in the route, we fetch from the edit service/catalog
        // The title can come from the route if present, otherwise just use the ID
        Component title = route.title().orElse(Component.literal(entryId.value()));

        var yaclBuilder = YetAnotherConfigLib.createBuilder()
                .title(Component.translatable("gui.treeify.config.detail.title", title))
                .save(() -> context.saveService().savePendingChanges());

        ConfigCategory.Builder categoryBuilder = ConfigCategory.createBuilder()
                .name(Component.translatable("gui.treeify.category.details"));

        OptionGroup.Builder settingsGroup = OptionGroup.createBuilder()
                .name(Component.translatable("gui.treeify.group.settings"));

        settingsGroup.option(Option.<Boolean>createBuilder()
                .name(Component.translatable("gui.treeify.option.enabled"))
                .binding(
                        true,
                        () -> context.editService().isEnabled(entryId),
                        val -> context.editService().setEnabled(entryId, val)
                )
                .controller(BooleanControllerBuilder::create)
                .build());

        settingsGroup.option(Option.<Float>createBuilder()
                .name(Component.translatable("gui.treeify.option.density_multiplier"))
                .binding(
                        1.0f,
                        () -> context.editService().getDensityMultiplier(entryId),
                        val -> context.editService().setDensityMultiplier(entryId, val)
                )
                .controller(opt -> FloatSliderControllerBuilder.create(opt).range(0.0f, 5.0f).step(0.1f))
                .build());

        settingsGroup.option(Option.<Integer>createBuilder()
                .name(Component.translatable("gui.treeify.option.height_delta"))
                .binding(
                        0,
                        () -> context.editService().getHeightDelta(entryId),
                        val -> context.editService().setHeightDelta(entryId, val)
                )
                .controller(opt -> IntegerFieldControllerBuilder.create(opt).min(-20).max(20))
                .build());

        categoryBuilder.group(settingsGroup.build());

        // Add Biome Overrides button as a group with a boolean detail controller, or just a simple button if YACL 3 supports it
        // YACL 3 doesn't have a simple button option easily, so we can use a boolean with a detail button controller
        // for navigating to the biome overrides.
        
        yaclBuilder.category(categoryBuilder.build());

        return yaclBuilder.build().generateScreen(parent);
    }
}
